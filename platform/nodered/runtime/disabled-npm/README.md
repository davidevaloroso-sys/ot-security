# Disabled runtime package manager

This local package replaces the `npm` dependency of Node-RED's registry through
the root runtime override. It is intentionally identified as
`@ot-security/disabled-npm`, not as an upstream npm release.

Node-RED resolves `npm/package.json` and `bin/npm-cli.js` at startup even when
installation is disabled. The adapter satisfies that path lookup and rejects
every invocation, including version probes. It neither performs installation nor
reports a fake successful version. No supplied arguments or environment values
are echoed.

The OT runtime already disables palette installation, uploads and automatic
module installation. Nodes and flows are built and tested with the image. Build
tools still use the real npm CLI outside this runtime. Removing the unused npm
bundle also removes its vulnerable bundled dependencies; no CVE is excluded and
no installed package version is rewritten to influence the scanner.

The runtime `.npmrc` sets `install-links=true` so npm installs this local package
as a real directory instead of a symlink. Preserve that setting when regenerating
the lockfile and copy it into the image: it also avoids stale lower-layer npm
files being attributed to a directory replaced by a symlink during image scans.
