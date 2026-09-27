import json
import queue
import ssl
import threading
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
import pandas as pd
import pytest
import paho.mqtt.client as mqtt
from ot_common import SubscriptionHealth, build_mqtt_client, threshold, validate_payload


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf'), 10**1000, True, None, '25'])
def test_reject_invalid_value(payload, value):
    payload['value'] = value
    with pytest.raises(ValueError): validate_payload(payload, 'temp')


@pytest.mark.parametrize('field,value', [('unit',None),('unit','%'),('ts',-1),('ts',True),('device',''),('in_range',1)])
def test_reject_contract(payload, field, value):
    payload[field] = value
    with pytest.raises(ValueError): validate_payload(payload,'temp')


def test_unknown_topic(ia,payload):
    with pytest.raises(ValueError): ia.evaluate_payload(payload,'unknown')


@pytest.mark.parametrize('value', ['NaN','inf','-0.1','1.1'])
def test_invalid_threshold(monkeypatch,value):
    monkeypatch.setenv('ANOMALY_THRESHOLD',value)
    with pytest.raises(ValueError): threshold()


def test_tls_secure_defaults(monkeypatch):
    monkeypatch.setenv('MQTT_USERNAME','test')
    monkeypatch.setenv('MQTT_PASSWORD','test-only')
    client=build_mqtt_client('test')
    assert client._ssl_context.verify_mode == ssl.CERT_REQUIRED
    assert client._ssl_context.check_hostname
    assert not client._clean_session
    assert client._callback_api_version == mqtt.CallbackAPIVersion.VERSION2


def test_plaintext_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setenv('MQTT_TLS','false')
    with pytest.raises(ValueError): build_mqtt_client('test')


def test_readiness_requires_all_qos1_subacks(tmp_path):
    health=SubscriptionHealth(['a','b'])
    client=Mock();client.subscribe.return_value=(0,10)
    health.on_connect(client,None,None,0,None)
    assert not (tmp_path/'ot-ready').exists()
    health.on_subscribe(client,None,10,[SimpleNamespace(value=1),SimpleNamespace(value=128)],None)
    assert not (tmp_path/'ot-ready').exists()
    health.on_subscribe(client,None,10,[SimpleNamespace(value=1)]*2,None)
    assert (tmp_path/'ot-ready').exists()
    health.on_disconnect(client,None,None,1,None)
    assert not (tmp_path/'ot-ready').exists()
    health.on_connect(client,None,None,0,None)
    assert client.subscribe.call_count == 2


@pytest.mark.parametrize('classes', [[0],[1],[1,2]])
def test_reject_model_classes(ia,classes):
    with pytest.raises(ValueError): ia.anomaly_index(SimpleNamespace(classes_=classes))


@pytest.mark.parametrize('score,alert', [(0.6,False),(0.7,True),(0.9,True)])
def test_runtime_threshold_and_class_order(ia,payload,score,alert):
    ia.model=SimpleNamespace(classes_=np.array([1,0]),predict_proba=lambda _: [[score,1-score]])
    result=ia.evaluate_payload(payload,ia.MQTT_TOPIC_TEMP)
    assert result['model_alert'] is alert
    assert result['model_anomaly_score']==score
    assert result['event_id']==ia.evaluate_payload(payload,ia.MQTT_TOPIC_TEMP)['event_id']


def message(ia,payload):
    return SimpleNamespace(payload=json.dumps(payload).encode(),topic=ia.MQTT_TOPIC_TEMP,mid=3,qos=1)


def test_callback_only_enqueues(ia,payload):
    client=Mock(); processor=ia.Processor(client)
    processor.on_message(client,None,message(ia,payload))
    client.publish.assert_not_called();client.ack.assert_not_called()
    assert processor.messages.qsize()==1


def test_ack_only_after_alert_confirmation(ia,payload):
    ia.model=SimpleNamespace(classes_=np.array([0,1]),predict_proba=lambda _: [[0.1,0.9]])
    client=Mock();client.ack.return_value=0
    info=Mock(rc=0); client.publish.return_value=info
    info.is_published.side_effect=[False,True]
    info.wait_for_publish.side_effect=lambda **_: client.ack.assert_not_called()
    ia.Processor(client).process(message(ia,payload))
    assert info.wait_for_publish.call_count==2
    assert client.publish.call_args.kwargs['qos']==1
    client.ack.assert_called_once_with(3,1)


def test_publish_failure_does_not_ack(ia,payload):
    ia.model=SimpleNamespace(classes_=[0,1],predict_proba=lambda _: [[0,1]])
    client=Mock(); client.publish.return_value=SimpleNamespace(rc=15)
    with pytest.raises(RuntimeError): ia.Processor(client).process(message(ia,payload))
    client.ack.assert_not_called()


def test_invalid_message_explicitly_discarded(ia,payload,caplog):
    client=Mock();client.ack.return_value=0
    payload['value']=float('nan')
    ia.Processor(client).process(message(ia,payload))
    client.ack.assert_called_once();client.publish.assert_not_called()
    assert 'Rejected' in caplog.text


def test_queue_overflow_fails_without_ack(ia,payload):
    client=Mock();processor=ia.Processor(client)
    processor.messages=queue.Queue(maxsize=1)
    processor.on_message(client,None,message(ia,payload))
    processor.on_message(client,None,message(ia,payload))
    assert processor.failed.is_set()
    client.ack.assert_not_called()


def test_shutdown_leaves_unconfirmed_input_unacked(ia,payload):
    ia.model=SimpleNamespace(classes_=[0,1],predict_proba=lambda _: [[0,1]])
    client=Mock();client.publish.return_value=Mock(rc=0)
    processor=ia.Processor(client);processor.stop.set()
    processor.process(message(ia,payload))
    client.ack.assert_not_called()


def dataset():
    return pd.DataFrame([{'value':20+i,'tipo':'temp','unit':'C','is_anomaly':i%2} for i in range(20)])


@pytest.mark.parametrize('column,value',[('value',float('inf')),('value',None),('is_anomaly',0.5),('unit','K')])
def test_training_rejects_invalid_rows(training,column,value):
    data=dataset().astype({column: object});data.loc[0,column]=value
    with pytest.raises(ValueError): training.validate_dataset(data)


def test_training_rejects_single_class(training):
    data=dataset();data['is_anomaly']=0
    with pytest.raises(ValueError): training.validate_dataset(data)


def test_metrics_measure_runtime_decision(training):
    metrics=training.runtime_metrics([0,1],[0.1,0.6],0.7)
    assert metrics['confusion_matrix']==[[1,0],[1,0]]
    assert metrics['classification_report']['1']['recall']==0


def test_quality_gate_is_enforced(training,monkeypatch):
    monkeypatch.setenv('MIN_ANOMALY_RECALL','0.9')
    metrics={'runtime':training.runtime_metrics([0,1],[0.1,0.6],0.7)}
    assert not training.check_quality(metrics)
    assert metrics['quality_status']=='failed'


def test_real_pipeline_roundtrip(training,ia,payload,tmp_path):
    import joblib
    data=training.validate_dataset(dataset())
    estimator=training.build_pipeline().fit(data[['value','tipo','unit']],data.is_anomaly)
    path=tmp_path/'model.joblib';joblib.dump(estimator,path)
    ia.model=joblib.load(path)
    result=ia.evaluate_payload(payload,ia.MQTT_TOPIC_TEMP)
    assert 0<=result['model_anomaly_score']<=1


def test_simulator_preserves_failure(simulator,monkeypatch):
    client=Mock()
    monkeypatch.setattr(simulator,'build_client',lambda:client)
    def fail(_): raise RuntimeError('injected')
    monkeypatch.setattr(simulator,'publish_loop',fail)
    with pytest.raises(RuntimeError,match='injected'): simulator.main()
    client.disconnect.assert_called_once(); client.loop_stop.assert_called_once()


def test_simulator_requires_positive_interval(simulator,monkeypatch):
    monkeypatch.setattr(simulator,'MQTT_BROKER','localhost')
    monkeypatch.setattr(simulator,'PUBLISH_INTERVAL',0)
    with pytest.raises(ValueError):simulator.build_client()


def test_model_metadata_mismatch_is_rejected(ia,tmp_path,monkeypatch):
    path=tmp_path/'model.joblib';path.write_bytes(b'not-loaded')
    metadata={'threshold':0.6,'dependencies':{},'model_sha256':'unused'}
    (tmp_path/'training_metrics.json').write_text(json.dumps(metadata))
    monkeypatch.setattr(ia,'MODEL_PATH',path)
    with pytest.raises(ValueError,match='threshold'):ia.load_model()
    metadata['threshold']=ia.ANOMALY_THRESHOLD
    (tmp_path/'training_metrics.json').write_text(json.dumps(metadata))
    with pytest.raises(ValueError,match='hash'):ia.load_model()


def test_inference_failure_is_not_silently_discarded(ia,payload):
    ia.model=SimpleNamespace(classes_=[0,1],predict_proba=lambda _: [[float('nan'),1]])
    client=Mock();processor=ia.Processor(client)
    processor.on_message(client,None,message(ia,payload))
    processor.run()
    assert processor.failed.is_set()
    client.ack.assert_not_called()


def test_quality_failure_removes_old_model(training,tmp_path,monkeypatch):
    path=tmp_path/'model.joblib';path.write_bytes(b'old')
    monkeypatch.setattr(training,'MODEL_PATH',path)
    monkeypatch.setattr(training,'load_dataset',lambda _: (_ for _ in ()).throw(ValueError('invalid data')))
    with pytest.raises(ValueError): training.main()
    assert not path.exists()


def test_normal_reading_acknowledged_without_alarm(ia,payload):
    ia.model=SimpleNamespace(classes_=[0,1],predict_proba=lambda _: [[0.9,0.1]])
    client=Mock();client.ack.return_value=0
    ia.Processor(client).process(message(ia,payload))
    client.publish.assert_not_called();client.ack.assert_called_once_with(3,1)
