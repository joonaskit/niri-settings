#!/usr/bin/env bash
# Cut a release: bump the version everywhere, test, commit, tag and push.
#
#   scripts/release.sh 0.2.0 "Short release notes."
#   scripts/release.sh 0.2.0 "Notes" --no-push    # stop after the local tag
#   scripts/release.sh 0.2.0 "Notes" --yes        # do not ask before pushing
#
# Pushing the v<version> tag starts .github/workflows/release.yml, which builds
# the packages and publishes the GitHub release.
set -euo pipefail

usage() { sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }

version=${1:-}
notes=${2:-}
[[ -n $version && -n $notes ]] || usage
shift 2
push=ask
for arg in "$@"; do
    case $arg in
        --no-push) push=no ;;
        --yes|-y) push=yes ;;
        *) usage ;;
    esac
done

die() { echo "release: $*" >&2; exit 1; }

[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "version must look like 1.2.3, got '$version'"
cd "$(git rev-parse --show-toplevel)"
[[ -z $(git status --porcelain) ]] || die "the working tree has uncommitted changes"
branch=$(git branch --show-current)
[[ $branch == main ]] || echo "release: note, releasing from '$branch', not main" >&2
git rev-parse -q --verify "refs/tags/v$version" >/dev/null && die "tag v$version already exists"

current=$(python3 -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')
python3 - "$current" "$version" <<'EOF' || die "version $version is not newer than $current"
import sys
old, new = (tuple(map(int, v.split("."))) for v in sys.argv[1:])
sys.exit(0 if new > old else 1)
EOF

echo "release: $current -> $version"

# Edit the four files that carry the version. tests/test_release.py checks they agree.
python3 - "$version" "$notes" <<'EOF'
import datetime, html, re, sys
version, notes = sys.argv[1], sys.argv[2]
today = datetime.date.today()

def edit(path, pattern, repl, count=1):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    new, n = re.subn(pattern, repl, text, count=count, flags=re.M)
    if n != count:
        sys.exit(f"release: could not update {path} ({pattern!r})")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(new)
    return text

edit("pyproject.toml", r'^version = "[^"]*"', f'version = "{version}"')
edit("niri_settings/__init__.py", r'^__version__ = "[^"]*"', f'__version__ = "{version}"')

spec = "packaging/niri-settings.spec"
with open(spec, encoding="utf-8") as fh:
    # Reuse the packager name from the newest changelog entry.
    packager = re.search(r"^%changelog\n\* \S+ \S+ \d+ \d+ (.+?) - ", fh.read(), re.M).group(1)
edit(spec, r"^Version:(\s*)\S+", rf"Version:\g<1>{version}")
edit(spec, r"^Release:(\s*)\S+", r"Release:\g<1>1%{?dist}")
stamp = today.strftime("%a %b %d %Y")
bullets = "\n".join(f"- {line.strip()}" for line in notes.splitlines() if line.strip())
edit(spec, r"^%changelog\n", lambda m: f"%changelog\n* {stamp} {packager} - {version}-1\n{bullets}\n\n")

paras = "\n".join(f"        <p>{html.escape(line.strip())}</p>"
                  for line in notes.splitlines() if line.strip())
release = (f'    <release version="{version}" date="{today.isoformat()}">\n'
           f"      <description>\n{paras}\n      </description>\n    </release>\n")
edit("data/io.github.joonaskit.NiriSettings.metainfo.xml", r"^  <releases>\n",
     lambda m: m.group(0) + release)
EOF

echo "release: running the tests"
if ! QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -t . ; then
    echo "release: tests failed; the version edits are left in the tree (git checkout . to undo)" >&2
    exit 1
fi

git add pyproject.toml niri_settings/__init__.py packaging/niri-settings.spec \
    data/io.github.joonaskit.NiriSettings.metainfo.xml
git commit -q -m "Release $version" -m "$notes"
git tag -a "v$version" -m "niri settings $version" -m "$notes"
echo "release: committed and tagged v$version"

if [[ $push == ask ]]; then
    read -r -p "Push $branch and v$version to origin? [y/N] " answer
    [[ $answer == [yY]* ]] && push=yes || push=no
fi
if [[ $push == yes ]]; then
    git push origin "$branch" "v$version"
    echo "release: pushed; the Release workflow builds and publishes it"
else
    echo "release: not pushed. When ready: git push origin $branch v$version"
fi
