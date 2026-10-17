# 「デュアル4K対応」のUSB-CドックでMacも2画面に拡張できる？ チップ上限と接続方式の確認

> Windows向けに「USB-C 1本で4K 2画面出力」と書かれたドックをMacBookにつないだとき、2枚のモニターに同じ画面しか映らない（ミラーリングになる）原因と選び方を整理します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/dual-4k-dock-mac-mst-displaylink-thunderbolt-guide
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/dual-4k-dock-mac-mst-displaylink-thunderbolt-guide.csv
- **Category**: Hardware & Power Electronics
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- MacBookに接続できる外部ディスプレイの最大台数は搭載されているAppleシリコンのチップ世代・グレード（無印 / Pro / Max）と解像度・リフレッシュレートによって厳密に決まっている。
- Apple公式サポート文書では、たとえばM5 Pro搭載MacBook Proでは最大3台まで対応する一方、フタ（クラムシェル）を閉じてもサポート上限台数自体は増えないモデルがあることなど、世代別の条件が明記されている。
- 高価なドックを買う前に、まず自分のMacの型番が標準で何画面まで対応しているかをApple公式一覧で調べ、1本のケーブルで2画面を別々に扱うにはThunderboltネイティブ対応ドックが必要かを確認する。


## 選択肢の比較表
| 確認するステップ | 見るべき仕様箇所 | よくある勘違い | 対処・選び方の方向性 |
| --- | --- | --- | --- |
| 1. Mac本体のチップ別上限 | Apple公式のモデル別外部ディスプレイ接続台数 | どのMacBookでもドックを挿せば2〜3画面に増やせる | M3 / M4 / M5等の無印・Pro・Maxごとの上限とフタ開閉条件を確認 |
| 2. ドックの映像分岐方式 | Thunderbolt対応か、USB-C（DP MST）のみか | Windowsで2画面拡張できるUSB-CハブならMacでも同じように動く | Macで1ポートから2画面拡張するならmacOSでの2画面拡張対応表記を確認 |
| 3. ドライバ方式（DisplayLink等） | 専用ソフトウェア（画面収録権限等）の要否 | ケーブルを挿すだけで標準出力と同じように動く | CPU負荷や著作権保護動画（HDCP）の制限を許容できるかで判断 |

## 詳細解説・原因分析
### ドックを選ぶ前に自分のMacが何枚の外部ディスプレイに対応しているかを調べる
「USB-Cドックを買えばモニターを2枚・3枚に増やせる」と考えて周辺機器を探す前に、まず確認すべきなのはMac本体側のハードウェア上限です。Apple公式サポート文書（How many displays can be connected to MacBook Pro）にある通り、同時に使用できる外部ディスプレイの台数は、搭載されているチップ（M2 / M3 / M4 / M5およびそれぞれの無印・Pro・Max）と、各ディスプレイの解像度・リフレッシュレートによって決まります。また、世代やチップによっては「本体のフタを閉じたときだけ2枚目が使えるモデル」と「フタを閉じても接続できる外部ディスプレイの上限台数が変わらないモデル（M5 Proなど）」が明確に分かれています。
参照: [Apple Support：How many displays can be connected to MacBook Pro](https://support.apple.com/en-us/101571)

### Windows向けの安価な「デュアルHDMI USB-Cハブ」はMacで同じ画面になりやすい
通販サイトで数千円〜1万円前後で売られている「USB-C 1本からHDMI 2ポートへ出力」というハブの多くは、DisplayPortのMST（Multi-Stream Transport）という分岐仕組みを前提に作られています。Windows PCではこの方式で2枚のモニターへ別々の画面（拡張デスクトップ）を表示できますが、macOSの標準出力仕様では1つのUSB-C（DP Alt Mode）ストリームからのMSTによる複数画面拡張がサポートされていません。そのため、商品ページの小さな注意書きに「※macOSでは2台の外部モニターはミラーリング（同じ画面）表示になります」と書かれているケースが多々あります。
参照: [Apple Support：How many displays can be connected to MacBook Pro](https://support.apple.com/en-us/101571)

### ケーブル1本で2画面を拡張したいならThunderboltドックか2本直挿しを比較する
Mac本体が2台以上の外部ディスプレイに対応しているモデルであり、かつケーブル1本だけで2枚のモニターへ別々の画面を出したい場合は、単なるUSB-Cマルチハブではなく、macOSでのデュアルディスプレイ拡張に対応した「Thunderbolt 4 / 5ドック」を選ぶ必要があります。ただしThunderboltドックは本体価格が高いため、「充電と1枚目のモニターはドック経由にし、2枚目のモニターだけはMac本体の別のThunderboltポートやHDMIポートへ直接挿す」という運用が許容できるなら、高価なドックへ買い替えなくても手持ちのケーブルだけで解決できます。
参照: [Apple Support：How many displays can be connected to MacBook Pro](https://support.apple.com/en-us/101571)

## 記事の範囲
2026年10月16日にApple公式サポート文書（MacBook Proに接続できるディスプレイの台数）を確認して整理した記事です。特定のサードパーティ製ドック製品での相性テストは行っていません。


## 参考資料
- [Apple Support：How many displays can be connected to MacBook Pro](https://support.apple.com/en-us/101571)

## 次に考えたいこと
- [USB4外付けSSD、公称40Gbpsだけで選んでいい？](https://nodus-lab.pages.dev/articles/external-ssd-usb4-40gbps-sustained-write-thermal-throttling)
- [MacでローカルLLMは動く？必要メモリとGPUとの選び方](https://nodus-lab.pages.dev/articles/local-llm-hardware-mac-unified-memory-vs-rtx-gpu-tokens-per-watt)
