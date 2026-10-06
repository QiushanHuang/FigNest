# Third-party notices

The FigNest 4.3.0 macOS package includes the following runtime components. Original
license and copyright notices are retained under `assets/licenses` in this source
package and under `Contents/Resources/assets/licenses` in the application.
`Contents/Resources/THIRD_PARTY_NOTICES.md` accompanies the application.

| Component | Version / notice |
| --- | --- |
| CPython | 3.14.7 — [PSF license and historical notices](assets/licenses/Python-3.14.7-LICENSE.txt) |
| PyInstaller bootloader | 6.22.3 — [COPYING and bootloader exception](assets/licenses/PyInstaller-6.22.3-COPYING.txt) |
| OpenSSL | 3.6.4 — [Apache 2.0 license](assets/licenses/OpenSSL-3.6.4-LICENSE.txt) |
| Expat incorporated in CPython | [MIT notice](assets/licenses/CPython-Expat-COPYING.txt) |
| mpdecimal | 4.0.1 — [copyright and BSD notice](assets/licenses/Mpdecimal-COPYRIGHT.txt) |
| Zstandard | 1.5.7 — [BSD license](assets/licenses/Zstandard-BSD-LICENSE.txt) |
| liblzma / XZ Utils | 5.8.4 — [0BSD license](assets/licenses/XZ-0BSD-LICENSE.txt), [component overview](assets/licenses/XZ-COPYING.txt) |
| SQLite | 3.53.4 — [public-domain dedication](https://www.sqlite.org/copyright.html) |

CPython and its dependencies are bundled by PyInstaller with library paths relocated
for standalone operation. FigNest does not patch their source code. System libraries,
AppKit and WebKit are supplied by macOS. The current packaged runtime requires
macOS 27+ on Apple Silicon; a source build inherits its selected runtime requirements.

The earlier Python 3.10.4, PyInstaller 5.1 and OpenSSL 1.1.1n notice files remain for
the historical 4.1.0 distribution. They do not describe the current runtime.

The icon is a project-created AI-assisted asset, not copied from another image
manager. Other products mentioned in documentation retain their names and rights.
