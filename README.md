# holodori-asset-tools

Decrypt, encrypt, download and extract holodori (hololive Dreams) game assets.

Inspired by [sssekai](https://github.com/mos9527/sssekai)

## Install

Download this repository, then run the command

```
pip install -e .
```

## Usage

The command is `holodori`.

Single files are always accepted (decrypt, encrypt, and extract)

```
holodori download ./assets [--filter REGEX] [--catalog octo_list.json]
holodori serve [--host 127.0.0.1] [--port 8000]
holodori decrypt ./in ./out
holodori encrypt ./in ./out [--kind bundle|resource]
holodori extract ./assets ./extracted
```

"Serving" the assets allows you to browse in browser the list of assets, and download any one you want.
Each assetbundle and each ACB/AWB/USM resource also gets an `extracted.zip` link that downloads the
asset plus every bundle it requires (per the octo dependency list), extracts them, and returns the
result as `extracted_{name}.zip`. The size shown next to the link is the total download it needs.

**We recommend using `holodori serve` for beginners! It lets you browse and download extracted assets.**

Assets live under two flat groups, `assetbundles/` and `resources/`. `download` and
`serve` pull the octo catalog (caching it to `--catalog`), fetch from the CDN and
decrypt on the fly. `decrypt`/`encrypt` operate on local files and key the header
mask on each file's name, so files must be named by their asset name.

`decrypt`, `encrypt` and `extract` accept either a single file or a directory as
their input.

`extract` extracts a given file or directory of assets. The following file types are extracted:
- Assetbundles (files inside are extracted)
- ACB/AWB files (**note: some ACB files rely on a separate AWB file - to extract those both files need to be downloaded**)
- USM files (*extracted as .ivf files, convert to mp4/mov with a converter like ffmpeg or online converter*)

Octo keys and app versions are fetched from our repository [here](https://github.com/HolodoriDB/holodori-app-protos/tree/main).

The library is usable directly:

```python
from holodori_asset_tools import catalog, crypto

cat = catalog.get("octo_list.json")
entry = cat.assetBundles[0]
raw = crypto.decrypt(open("SEvWEA", "rb").read(), entry.name)
```
