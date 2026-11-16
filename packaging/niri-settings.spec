%global appid io.github.joonaskit.NiriSettings

Name:           niri-settings
Version:        0.1.0
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
install -Dpm 0644 data/%{appid}.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/%{appid}.svg
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
%{_datadir}/icons/hicolor/scalable/apps/%{appid}.svg
%{_metainfodir}/%{appid}.metainfo.xml

%changelog
* Mon Nov 16 2026 Joonas Kitunen - 0.1.0-1
- First release
