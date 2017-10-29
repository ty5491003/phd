#!/usr/bin/env bash
usage() {
    echo "usage: $(basename $0)"
}
test -z "$1" || { usage; exit 1; }

set -eu

src="/Volumes/Orange/"
dst="/Volumes/Photo Library/"

if [[ ! -d "$src" ]]; then
    echo "fatal: '$src' not found" >&2
    exit 1
fi

if [[ ! -d "$dst" ]]; then
    echo "fatal: '$dst' not found" >&2
    exit 1
fi

set -x

# rm-dsstore "$src"
rsync -avh --delete "$src" "$dst" \
    --exclude "*.lrcat-journal" \
    --exclude "*.lrcat.lock" \
    --exclude "*.lrdata" \
    --exclude "._.DS_Store" \
    --exclude ".DS_Store" \
    --exclude ".sync.ffs_db" \
    --exclude "/.fseventsd" \
    --exclude "/.Spotlight-V100" \
    --exclude "/.TemporaryItems" \
    --exclude "/.Trashes" \
    --exclude "/.VolumeIcon.icns" \
    --exclude "/.VolumeIcon.ico" \
    --exclude "/autorun.inf" \
    --exclude "Mobile Downloads.lrdata"
