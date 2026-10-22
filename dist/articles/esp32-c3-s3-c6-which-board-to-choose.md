# ESP32比較表：C3・S3・C6はどれを買う？ ラズパイPico（RP2040/RP2350）やXIAOとの違い

> C3・S3・C6を、温湿度計・音声・スマートホームの用途から比較。ボード単価だけでは見えない費用も整理します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/esp32-c3-s3-c6-which-board-to-choose
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/esp32-c3-s3-c6-which-board-to-choose.csv
- **Category**: Hardware & Power Electronics
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-13

## 選び方の要点
- 温湿度の送信や小さな制御なら、まずC3で必要な端子とソフト対応を確認。
- 音声・カメラ・画面はS3を候補に。チップ名だけでなくPSRAM搭載ボードを比較する。
- Thread・Zigbeeが目的ならC6を候補に。Wi-Fi 6対応だけで速度や省電力の優位は決められない。


## 選択肢の比較表
| 候補 | 通信・処理の特徴 | 候補になる用途 | 購入前に確認すること |
| --- | --- | --- | --- |
| ESP32-C3 | 単コア RISC-V / Wi-Fi 4 / Bluetooth LE | センサー送信、シンプルな制御 | 必要なGPIO、USB接続方式、基板の待機電流 |
| ESP32-S3 | デュアルコア Xtensa / Wi-Fi 4 / Bluetooth LE | 音声、カメラ、画面付き工作 | PSRAM搭載量、ピン配置、周辺機器の対応 |
| ESP32-C6 | 単コア RISC-V / 2.4GHz Wi-Fi 6 / Bluetooth LE / 802.15.4 | Thread・Zigbeeを使う工作 | 利用フレームワークと接続先の対応、ボーダールーターの要否 |

## 詳細解説・原因分析
### 最初に決めるのは、完成させたいもの
「一番高性能なESP32」を選ぶ前に、センサーの種類、必要なピン数、電源、通信方式を書き出します。温湿度を数分ごとに送る装置と、マイクで音声を取り込む装置では、必要なメモリも処理能力も違います。上の3種類は出発点であり、ESP32全シリーズの網羅比較ではありません。

### チップの比較と、開発ボードの比較を分ける
同じS3でもPSRAMの有無・容量、Flash容量、USB端子、レギュレーター、使えるGPIOピンやその配置が異なります。製品ページのチップ名だけで決めず、正確なボード型番と回路図を確認してください。Bluetooth LEに対応していても、Bluetooth Classicに対応しているとは限りません。

### 安さは「動くところまで」の合計で比べる
基板価格に、送料、電源、ケーブル、センサー、ケース、足りない工具を足します。電池駆動なら開発ボード全体の待機電流を調べる必要があります。チップのディープスリープ公称値を、そのまま完成品の電池寿命に換算することはできません。安い基板でも、資料やピン配置が不明なら調査時間が増えます。

### C6を選ぶ理由は、使う通信規格にある
C6は2.4GHzのWi-Fi 6と802.15.4を備えます。ThreadやZigbeeを使いたいときの候補ですが、チップが対応していることと、使いたいファームウェアで目的の機能が動くことは別です。接続先のハブ、ボーダールーター、フレームワークの対応を先に確認します。

### 次に実機で比べたいこと
同じセンサーと送信間隔で、USB給電時の平均電力、電池駆動時の待機電流、接続の復帰時間を測ると選び方に役立ちます。国内購入と海外購入の送料込み総額、初回書き込みまでの所要時間も記録したい項目です。現段階ではこれらを測っていないため、価格ランキングや電池寿命の順位は付けていません。

## よくある疑問と回答 (FAQ)
### Q. ESP32-C3、ESP32-S3、ESP32-C6は用途別にどう使い分ければいいですか？
A. 温湿度センサーなど小型・省ピン用途なら安価なC3、カメラ・音声処理・液晶表示などPSRAMやAI命令が必要ならS3、ThreadやZigbee（IEEE 802.15.4）によるMatterスマートホーム機器を作りたいならC6を選びます。

### Q. ESP32シリーズとRaspberry Pi Pico W（RP2040 / RP2350）はどう比較すればいいですか？
A. Wi-Fi・BLE通信やESPHome連携が主目的なら情報量と周辺機能が豊富なESP32（C3/S3/C6）が手軽です。一方、PIO（プログラマブルI/O）による厳密なタイミング制御やMicroPythonの扱いやすさを重視するならRaspberry Pi Picoシリーズが向いています。

### Q. 通常のDevKit開発ボードとSeeed Studio XIAO ESP32シリーズの違いは何ですか？
A. 標準のDevKitC等はピン数が多くブレッドボード実験に向いていますが、XIAO ESP32（C3/S3/C6）は切手サイズの超小型基板にリチウムイオン電池の充電回路と外部アンテナ端子がまとまっており、小型ケースへの組み込みに有利です。

## 記事の範囲
公式資料を参照して選択の条件を整理した編集記事です。実機テスト、実売価格の調査、検索ボリュームの計測は行っていません。費用の数値は計算方法を示す仮定例であり、製品やサービスの現在価格・性能の保証ではありません。


## 参考資料
- [Espressif：ESP32シリーズの機能比較](https://docs.espressif.com/projects/esp-idf/en/v5.0/esp32s3/hw-reference/chip-series-comparison.html)
- [Espressif：ESP32-C6 データシート](https://www.espressif.com/sites/default/files/documentation/esp32-c6_datasheet_en.pdf)

## 次に考えたいこと
- [ESP32のDeepSleep消費電力：電池が計算より早く切れる理由と待機電流・復帰設計](https://nodus-lab.pages.dev/articles/esp32-deep-sleep-battery-life-board-quiescent-current)
- [ESP32-S3の2つのUSB端子（UARTとUSB OTG/JTAG）、どっちに挿す？](https://nodus-lab.pages.dev/articles/esp32-s3-dual-usb-ports-uart-native-otg-guide)
- [ESP32-C6でMatter・Threadを使うには？ ボーダールーターと必要機器の条件](https://nodus-lab.pages.dev/articles/esp32-c6-matter-thread-border-router-requirements)
- [自作CO₂センサーの選び方：実測式（SCD40/41）と推定式eCO₂（SGP30）の見分け方](https://nodus-lab.pages.dev/articles/co2-sensor-ndir-vs-eco2-tvoc-selection-guide)
