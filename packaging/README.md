# Packaging and releases

The app id is `io.github.joonaskit.NiriSettings`. It names the desktop entry, the icon,
the AppStream file and the Wayland app-id the window gets (for niri window rules).

## Build the RPM locally

Needs `rpm-build`, `git`, `python3-setuptools` and the build dependencies
(`dnf builddep packaging/niri-settings.spec`).

```
make -f .copr/Makefile srpm            # source RPM of HEAD into dist/
rpmbuild --rebuild dist/niri-settings-*.src.rpm
sudo dnf install ~/rpmbuild/RPMS/noarch/niri-settings-*.noarch.rpm
```

Without those tools on the host, build in a container:

```
podman run --rm -v "$PWD":/src:Z -w /src registry.fedoraproject.org/fedora:44 bash -c '
  dnf -y install git rpm-build make python3-devel python3-setuptools pyproject-rpm-macros "dnf-command(builddep)" &&
  make -f .copr/Makefile srpm &&
  dnf -y builddep dist/*.src.rpm &&
  { rpmbuild -rr dist/*.src.rpm --define "_srcrpmdir /tmp/br" || true; } &&
  dnf -y builddep /tmp/br/*.buildreqs.nosrc.rpm &&
  rpmbuild --rebuild dist/*.src.rpm --define "_rpmdir /src/dist"'
```

`%check` runs the whole test suite with `niri validate`, so a build that passes has
checked every schema default against the packaged niri.

## COPR

Create a project at copr.fedorainfracloud.org, add a package with source type **SCM**:

- Clone URL: `https://github.com/joonaskit/niri-settings`
- Spec file: `packaging/niri-settings.spec`
- SRPM build method: `make srpm` (uses `.copr/Makefile`)

Turn on the GitHub webhook in the project's Integrations to rebuild on every push, or build
only tags. Users then install with `dnf copr enable <owner>/niri-settings` and
`dnf install niri-settings`.

## Releasing a version

```
scripts/release.sh 0.2.0 "One line per change.
Another change."
```

From a clean `main`, the script:

1. checks the version is newer than the current one and the tag does not exist yet;
2. writes it to `pyproject.toml`, `niri_settings/__init__.py` and the spec (`Version`,
   `Release: 1`, a `%changelog` entry), and adds a `<release>` to the metainfo, with one
   changelog bullet or paragraph per line of the notes;
3. runs the tests (`tests/test_release.py` checks the four files agree), commits
   "Release 0.2.0" and makes an annotated `v0.2.0` tag;
4. asks before pushing the branch and the tag (`--yes` skips the question, `--no-push`
   stops after the local tag).

The pushed tag starts `.github/workflows/release.yml`. In a Fedora container it builds the
sdist, wheel, source RPM and noarch RPM (whose `%check` runs the whole suite against
Fedora's niri), then publishes a GitHub release with them attached. The notes are the
tag's notes followed by GitHub's generated list of merged pull requests. The spec's
`Source` is GitHub's archive of the tag, so COPR can build it once the tag exists.

If a release fails after tagging, fix it and cut the next patch version rather than
moving a published tag.

## CI

`.github/workflows/ci.yml` runs `ruff check` and the test suite in a Fedora container on
every pull request and every push to `main`.
