# holodori-asset-tools

**DOES NOT REQUIRE THE GAME INSTALLED ON PC!!! NO EXTRA SETUP IS REQUIRED.**

Decrypt, encrypt, download and extract holodori (hololive Dreams) game assets.

Inspired by [sssekai](https://github.com/mos9527/sssekai)

**We recommend using `holodori serve` for beginners! It lets you browse and download extracted assets.**

## Game Data Source
Octo keys and app versions are fetched from our repository [here](https://github.com/HolodoriDB/holodori-app-protos/tree/main). When the game updates, usually it can take a few minutes up to a few hours to automatically extract the game details. In rare cases, updates can break this process; in which case an update will be pushed ASAP to the `holodori-app-protos` repository (but can take a while).

Sometimes (hasn't happened yet) this may be a breaking change that requires a `holodori-asset-tools` library update.

## Install

```
pip install holodori-asset-tools
```

## CLI Usage

The command is `holodori`.

Single files are always accepted (decrypt, encrypt, and extract)

```
holodori download ./assets [--filter REGEX] [--catalog octo_list.json]
holodori serve [--host 127.0.0.1] [--port 8000]
holodori decrypt ./in ./out
holodori encrypt ./in ./out [--kind bundle|resource]
holodori extract ./assets ./extracted
```

"Serving" the assets allows you to browse in browser the list of assets, and download any one you want. You can also download assetbundle-type files as extracted zips!

Assets for this game are under two groups without any nesting; `assetbundles/` and `resources/`. The library's `download` and `serve` commands automatically fetch the octo catalog (use `--catalog` to change location).

The `decrypt`/`encrypt` require the asset's file name, so files must be named by their asset name!

`extract` extracts a given file or directory of assets. The following file types are extracted:
- Assetbundles (files inside are extracted)
- ACB/AWB files (**note: some ACB files rely on a separate AWB file - to extract those both files need to be downloaded**)
- USM files (*extracted as .ivf files, convert to mp4/mov with a converter like ffmpeg or online converter - TODO convert*)

## Programmatic Usage
The library is usable directly:

```python
from holodori_asset_tools import catalog, crypto

cat = catalog.get("octo_list.json")
entry = cat.assetBundles[0]
raw = crypto.decrypt(open("SEvWEA", "rb").read(), entry.name)
```
