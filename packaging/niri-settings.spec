%global appid io.github.joonaskit.NiriSettings

Name:           niri-settings
Version:        0.2.1
Release:        1%{?dist}
Summary:        Settings app for the niri compositor

# The app is GPL-3.0-or-later; the bundled Inter and JetBrains Mono fonts are OFL-1.1.
License:        GPL-3.0-or-later AND OFL-1.1
URL:            https://github.com/joonaskit/niri-settings
Source:         %{url}/archive/v%{version}/%{name}-%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  desktop-file-utils
BuildRequires:  appstream
# For the test suite in %%check
BuildRequires:  niri
BuildRequires:  python3-pyside6
BuildRequires:  libxkbcommon

Requires:       niri
Requires:       python3-pyside6
# Loaded with ctypes to place keys on the key-bindings map
Requires:       libxkbcommon
Requires:       hicolor-icon-theme
Provides:       bundled(font(inter))
Provides:       bundled(font(jetbrainsmono))

%description
A settings app for the niri Wayland compositor. It edits your KDL config in
place, keeps comments and formatting, and never writes a file that
`niri validate` rejects. Pages cover layout, appearance, animations, displays,
input, key bindings, window rules, startup apps and the raw config files, with
a live preview, a diff of unsaved changes and snapshots of every save.

%prep
%autosetup -n %{name}-%{version}

%generate_buildrequires
%pyproject_buildrequires

%build
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files -l niri_settings
install -Dpm 0644 data/%{appid}.desktop %{buildroot}%{_datadir}/applications/%{appid}.desktop
install -Dpm 0644 icons/niri-settings.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/%{appid}.svg
for size in 16 24 32; do
    install -Dpm 0644 icons/niri-settings-small.svg \
        %{buildroot}%{_datadir}/icons/hicolor/${size}x${size}/apps/%{appid}.svg
done
install -Dpm 0644 icons/niri-settings-symbolic.svg \
    %{buildroot}%{_datadir}/icons/hicolor/symbolic/apps/%{appid}-symbolic.svg
install -Dpm 0644 data/%{appid}.metainfo.xml %{buildroot}%{_metainfodir}/%{appid}.metainfo.xml

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/%{appid}.desktop
appstreamcli validate --no-net %{buildroot}%{_metainfodir}/%{appid}.metainfo.xml
export QT_QPA_PLATFORM=offscreen
%{py3_test_envvars} %{python3} -m unittest discover -s tests -t .

%files -f %{pyproject_files}
%doc README.md
%{_bindir}/niri-settings
%{_datadir}/applications/%{appid}.desktop
%{_datadir}/icons/hicolor/*/apps/%{appid}.svg
%{_datadir}/icons/hicolor/symbolic/apps/%{appid}-symbolic.svg
%{_metainfodir}/%{appid}.metainfo.xml

%changelog
* Thu Nov 26 2026 Joonas Kitunen - 0.2.1-1
- An About page, pinned at the bottom of the sidebar, shows the version, links to the source, issues and release notes, and the license.
- Its system info lists the niri, Qt and Python versions, the config path and the write mode, and copies them for a bug report.

* Tue Nov 24 2026 Joonas Kitunen - 0.2.0-1
- Settings pages show each group as a bordered panel whose header sticks while scrolling and folds the group to a summary.
- Wide windows list the page's groups in an On this page index.
- Each setting marks an unsaved change and offers Undo; groups count set and unsaved values and can be reset.
- Setting cards in one row share the same height.

* Fri Nov 20 2026 Joonas Kitunen - 0.1.1-1
- Fix a startup error after upgrading: clear the QML cache when the app's QML files change.
- Fix a crash when an outside edit removes an include that has unsaved changes.

* Mon Nov 16 2026 Joonas Kitunen - 0.1.0-1
- First release
