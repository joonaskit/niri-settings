# Packaging and releases

The app id is `io.github.joonaskit.NiriSettings`. It names the desktop entry, the icon,
the AppStream file and the Wayland app-id the window gets (for niri window rules).

## Build the RPM locally

Needs `rpm-build`, `git` and the build dependencies (`dnf builddep packaging/niri-settings.spec`).

```
make -f .copr/Makefile srpm            # source RPM of HEAD into dist/
rpmbuild --rebuild dist/niri-settings-*.src.rpm
sudo dnf install ~/rpmbuild/RPMS/noarch/niri-settings-*.noarch.rpm
```

Without those tools on the host, build in a container:

```
podman run --rm -v "$PWD":/src:Z -w /src registry.fedoraproject.org/fedora:44 bash -c '
  dnf -y install git rpm-build make python3-devel pyproject-rpm-macros "dnf-command(builddep)" &&
  make -f .copr/Makefile srpm &&
  dnf -y builddep dist/*.src.rpm &&
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

1. Bump the version in `pyproject.toml`, `niri_settings/__init__.py`,
   `packaging/niri-settings.spec` (and its `%changelog`) and add a `<release>` to
   `data/io.github.joonaskit.NiriSettings.metainfo.xml`. `tests/test_release.py` fails if
   they disagree.
2. Run the tests, commit, then tag: `git tag v0.1.0 && git push --tags`. The spec's
   `Source` is GitHub's archive of that tag.
