# ESP32-S3（DevKitC-1等）にUSB端子が2つある理由：UART端子とUSB（OTG/JTAG）の使い分け

> ESP32-S3ボードに「UART（またはCOM）」と「USB（またはOTG）」の2つのUSB-C端子があるとき、プログラム書き込み・シリアル監視・USB機器エミュレーションでどちらを使うかを整理します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/esp32-s3-dual-usb-ports-uart-native-otg-guide
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/esp32-s3-dual-usb-ports-uart-native-otg-guide.csv
- **Category**: Hardware & Power Electronics
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- ESP32-S3開発ボードの2つのUSB端子は、外付け変換チップを通る「UART端子」と、S3チップ内部のUSB周辺回路（GPIO19/20）へ直結された「ネイティブUSB端子」に分かれている。
- 普段のプログラム書き込みやスリープを伴うシリアルログ確認で最もトラブルが少ないのは外付け変換チップ経由の「UART端子」である。
- ESP32-S3をUSBキーボード・マウス（HID）やUSBストレージとしてPCに認識させたい場合や、内蔵JTAGデバッグを使う場合は「ネイティブUSB端子」を使う。


## 選択肢の比較表
| 端子の種類（基板上の表記例） | 内部の接続先 | 向いている用途 | 気をつける制限（公式資料より） |
| --- | --- | --- | --- |
| UART端子（UART / COM） | ボード上のUSB-シリアル変換IC経由でUART0へ接続 | 初回の書き込み、Deep Sleepを含む開発時のログ監視 | USBキーボード等のネイティブUSB機器としては動作しない |
| ネイティブUSB端子：Serial/JTAGモード | ESP32-S3内蔵のUSB Serial/JTAGコントローラ（GPIO19/20） | 外付け変換ICなしでの書き込み、JTAGデバッグ、小型基板の自作 | Deep Sleepやピン再設定を行うとPCとの通信が切れる |
| ネイティブUSB端子：USB OTGモード | ESP32-S3内蔵のUSB OTG周辺回路（ソフトウェアUSBスタック） | USB HID（キーボード等）、CDC、マスストレージ等の実装 | アプリがクラッシュ・停止するとUSB通信も一緒に止まる |

## 詳細解説・原因分析
### 外付け変換チップ経由の端子とチップ直結のネイティブ端子がある
ESP32-S3の開発ボード（DevKitC系など）を手に取ると、「UART」と書かれた端子と「USB」と書かれた端子の2つが並んでいることがあります。これは単なる予備の電源端子ではありません。片方の「UART」端子は、基板上のUSB-シリアル変換チップ（CP2102NやCH343など）を経由してESP32-S3のシリアル通信ピンにつながっています。もう片方の「USB」端子は、ESP32-S3チップ自身が内蔵しているUSBインターフェース（GPIO19およびGPIO20のD-/D+信号線）へ直接つながっています。
参照: [Espressif ESP-IDF Guide：USB OTG Console (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/usb-otg-console.html)
参照: [Espressif ESP-IDF Guide：USB Serial/JTAG Controller Console (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/usb-serial-jtag-console.html)
参照: [Espressif：Chip Series Comparison](https://docs.espressif.com/projects/esp-idf/en/v5.0/esp32s3/hw-reference/chip-series-comparison.html)

### 内蔵のUSB Serial/JTAGとUSB OTGは同じ物理ピンを共有する別の機能
さらにESP-IDFの公式ドキュメントで区別されている通り、チップ直結の「USB」端子の奥には2つの異なる内部ハードウェアが存在します。1つはハードウェア固定の「USB Serial/JTAGコントローラ」で、プログラムの書き込みやシリアルモニター、JTAGデバッグを追加部品なしで行えます。もう1つは「USB OTGペリフェラル」で、TinyUSB等のソフトウェアスタックと組み合わせてESP32-S3自体をUSBキーボードやUSBメモリ、あるいはUSBホストとして動作させる機能です。両者は同じGPIO19/20ピンを共有しているため、用途に応じて切り替えて使います。
参照: [Espressif ESP-IDF Guide：USB OTG Console (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/usb-otg-console.html)
参照: [Espressif ESP-IDF Guide：USB Serial/JTAG Controller Console (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/usb-serial-jtag-console.html)

### Deep Sleepの実験やクラッシュ調査ではUART端子の方が切断されにくい
どちらの端子でもプログラムの書き込みやログ出力は可能ですが、公式ガイドにはネイティブUSB側ならではの制限が明記されています。たとえば内蔵のUSB Serial/JTAGやUSB OTGを使っている場合、プログラム内でGPIO19/20を別用途に再設定したり、チップがDeep Sleep（深睡眠モード）に入ったりすると、PC側から見たUSBデバイス自体が消失し、シリアルポートが切断されます。さらにUSB OTGコンソールでは、ソフトウェアがクラッシュして動作を止めるとUSB通信も同時に止まってしまいます。これに対し、外付け変換チップを通る「UART」端子であれば、ESP32-S3がスリープや再起動を繰り返してもPC側のCOMポートが維持されるため、電池駆動の実験やデバッグではUART端子につなぐ方が安定します。
参照: [Espressif ESP-IDF Guide：USB OTG Console (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/usb-otg-console.html)
参照: [Espressif ESP-IDF Guide：USB Serial/JTAG Controller Console (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/usb-serial-jtag-console.html)

### 小型ボードを買う前にどちらの方式で実装されているかを確認する
手のひらサイズの超小型ESP32-S3ボードでは、基板面積を節約するために外付けのUART変換チップを省き、ネイティブUSB端子1つだけを搭載している製品が多くあります。そうしたボードでも書き込みや通常の利用は問題なく行えますが、「書き込みモードに入りにくいときにBOOTボタンを押しながらリセットする操作が必要になる場合がある」「Deep Sleep中にシリアルポートが一度消える」といった挙動の違いをあらかじめ理解して選ぶと、購入後に故障と勘違いせずに済みます。
参照: [Espressif ESP-IDF Guide：USB OTG Console (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/usb-otg-console.html)
参照: [Espressif ESP-IDF Guide：USB Serial/JTAG Controller Console (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/usb-serial-jtag-console.html)
参照: [Espressif：Chip Series Comparison](https://docs.espressif.com/projects/esp-idf/en/v5.0/esp32s3/hw-reference/chip-series-comparison.html)

## よくある疑問と回答 (FAQ)
### Q. ESP32-S3-DevKitC-1などの「UART」と「USB」の2つのポートは普段どちらに挿せばいいですか？
A. 通常のプログラム書き込みやシリアルモニター確認、Deep Sleepの実験では、外付け変換ICを経由してリセット時もポートが切断されにくい「UART」端子に挿すのが最も安定します。

### Q. もう片方の「USB」端子（ネイティブUSB / GPIO19・20）はいつ使いますか？
A. ESP32-S3をPCからUSBキーボード・マウス（HID）やUSBメモリ（MSC）として認識させたい場合（USB OTG機能）や、外付けデバッガなしで内蔵USB Serial/JTAGデバッグを行う場合に使います。

## 記事の範囲
2026年10月16日にEspressif公式ESP-IDFプログラミングガイド（USB OTG Console、USB Serial/JTAG Controller Console、チップ比較表）を確認して整理した記事です。サードパーティ製互換ボードごとの回路差や給電電流の実測は行っていません。


## 参考資料
- [Espressif ESP-IDF Guide：USB OTG Console (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/usb-otg-console.html)
- [Espressif ESP-IDF Guide：USB Serial/JTAG Controller Console (ESP32-S3)](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-guides/usb-serial-jtag-console.html)
- [Espressif：Chip Series Comparison](https://docs.espressif.com/projects/esp-idf/en/v5.0/esp32s3/hw-reference/chip-series-comparison.html)

## 次に考えたいこと
- [ESP32比較（C3・S3・C6）：用途別の選び方とラズパイPico・XIAOとの違い](https://nodus-lab.pages.dev/articles/esp32-c3-s3-c6-which-board-to-choose)
- [ESP32-C6でMatter・Threadを使うには？ ボーダールーターと必要機器の条件](https://nodus-lab.pages.dev/articles/esp32-c6-matter-thread-border-router-requirements)
