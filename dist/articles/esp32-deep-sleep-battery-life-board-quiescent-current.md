# ESP32の電池持ちはチップのµA値だけで計算できる？ Deep Sleepと開発ボード待機電流の考え方

> データシート上のDeep Sleep電流は数〜数十µAなのに、一般的な開発ボードを電池で動かすと数日〜数週間で切れてしまう理由と、設定・給電で見直すポイントを整理します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/esp32-deep-sleep-battery-life-board-quiescent-current.html
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/esp32-deep-sleep-battery-life-board-quiescent-current.csv
- **Category**: Hardware & Power Electronics
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- チップ単体のDeep Sleep電流（数〜数十µA）が小さくても、一般的なUSB開発ボードには電源LED・電圧レギュレーター・USBシリアル変換ICが載っており、基板全体では待機中もより大きな電流が流れ続ける。
- 電池持ちは「スリープ中の待機電流」と「起床してWi-Fi接続・送信する数秒間の消費電流」の合計で決まるため、送信間隔と起床時間の短縮が直結する。
- ESPHomeのDeep Sleep中はネットワーク通信やOTA更新に一切応答しないため、運用前に保守手順とHome Assistant側の表示仕様を確認しておく必要がある。


## 選択肢の比較表
| 電力を消費する要素 | チップ単体の公称値だけで見えるか | 電池持ちを悪化させる主な原因 | 対策の方向性 |
| --- | --- | --- | --- |
| ESP32チップ本体のスリープ | 見える（データシート記載の対象） | 起床ピン設定や内部周辺回路の保持設定 | 必要な起床方法（タイマー / RTCピン）だけに絞る |
| 開発ボード上の周辺回路 | 見えない（基板設計に依存） | 常時点灯の電源LED、LDOレギュレーターの自己消費、USB変換IC | 電池駆動向け省電力基板を選ぶか3.3V直接給電を検討 |
| 起床時のWi-Fi接続・送信 | 見えない（通信環境に依存） | DHCP取得やWi-Fi再接続に毎回長い秒数がかかる | run_durationの最適化、固定IP化、送信間隔の見直し |
| 接続したセンサーモジュール | 見えない（外付け部品に依存） | スリープ中もセンサー側に通電し続けている | 低消費電力センサーの選定や計測時のみの通電制御 |

## 詳細解説・原因分析
### チップ単体のデータシート値と開発ボード全体の待機電流は別物として扱う
ESP32シリーズのデータシートには、Deep Sleepモード時の消費電流として数µA〜数十µAという非常に小さな値が記載されています。しかし、これはあくまで「ESP32チップ（またはモジュール）単体」の数値です。USB端子が付いた一般的な開発ボードには、5Vを3.3Vへ下げる電源レギュレーター（LDO）、USBシリアル変換チップ、そして通電中に光り続ける電源LEDが搭載されています。ESP32チップ自体が深いスリープに入っていても、これらの周辺部品が常時数mA（数千µA）を消費していれば、電池寿命はチップ単体の計算値から1桁以上短くなります。ESPHomeの公式ドキュメントでも、一部のボードではオンボードのUSBチップがDeep Sleepからの復帰や動作に影響する場合があり、3.3VピンとGNDへの別電源供給で回避できるケースが注記されています。
参照: [ESPHome Docs：Deep Sleep Component](https://esphome.io/components/deep_sleep/)
参照: [Espressif：Chip Series Comparison](https://docs.espressif.com/projects/esp-idf/en/v5.0/esp32s3/hw-reference/chip-series-comparison.html)

### スリープ電流と起床時の通信電流を分けて平均電流を試算する
電池が何日持つかを見積もる際は、スリープ中の待機分と、起床してWi-Fi送信を行う稼働分を分けて合算します。たとえば仮定の計算例として、10分（600秒）ごとに1回起き、1回の稼働時間（`run_duration`）が10秒でその間の平均電流を120mA、残り590秒のスリープ中の基板全体の待機電流を2mAと置いた場合、1サイクルの平均電流は `(120mA × 10秒 + 2mA × 590秒) ÷ 600秒 ＝ 3.97mA` となります。この仮定では、実効容量1,500mAhの電池を使っても `1,500mAh ÷ 3.97mA ≒ 約378時間（約15.7日）` で切れる計算になります。もし省電力設計の基板を使ってスリープ待機電流を0.1mA（100µA）まで下げ、稼働時間を3秒に短縮できれば、同じ仮定式で平均電流は約0.70mAとなり、約89日まで延びます（いずれも計算手順を示す仮定例であり、実機の保証値ではありません）。
参照: [ESPHome Docs：Deep Sleep Component](https://esphome.io/components/deep_sleep/)

### Deep Sleep中はOTA更新や通信に応答しないため保守方法を決めておく
ESPHomeの公式ドキュメント（Deep Sleep Component）には、「Deep Sleepモードの間、ノードはいかなる処理も行わず、OTA（無線アップデート）を含むすべてのネットワークトラフィックに応答しない」と明記されています。一度短い稼働時間と長いスリープ時間を書き込んでしまうと、次に設定を変更したくなったときにOTA書き込みのタイミングを合わせるのが難しくなります。高い場所やケース内に設置する前に、Home Assistant側からスリープ突入を一時停止させる仕組み（入力ヘルパーやMQTTフラグの監視など）を入れておくか、USBケーブルを挿し直しやすい配置にしておくことが重要です。
参照: [ESPHome Docs：Deep Sleep Component](https://esphome.io/components/deep_sleep/)

### スリープ中にHome Assistant側で「利用不可」になる挙動を確認する
もう一つの実務上の注意点として、デバイスがスリープに入った際にHome Assistantの画面上でセンサー値が「Unavailable（利用不可）」に変わってしまう現象があります。ESPHome公式ドキュメントでは、デバイスをHome Assistantへ登録した「あと」から `deep_sleep` コンポーネントを追加した場合にこの挙動が起きやすく、Home Assistant側で一度デバイスを削除して再登録することで防げると案内されています。電池持ちの測定を始める前に、まず10分程度の短い周期でスリープ復帰と画面表示が意図通り動くかを確かめます。
参照: [ESPHome Docs：Deep Sleep Component](https://esphome.io/components/deep_sleep/)

## 記事の範囲
2026年10月16日にESPHome公式ドキュメント（Deep Sleep Component）およびEspressif公式資料を確認して整理した記事です。記事内の電池寿命試算は仮定の電流値・稼働時間に基づく計算例であり、特定の開発ボードや電池での実測結果ではありません。


## 参考資料
- [ESPHome Docs：Deep Sleep Component](https://esphome.io/components/deep_sleep/)
- [Espressif：Chip Series Comparison](https://docs.espressif.com/projects/esp-idf/en/v5.0/esp32s3/hw-reference/chip-series-comparison.html)

## 次に考えたいこと
- [ESP32、結局どれを買えばいい？](https://nodus-lab.pages.dev/articles/esp32-c3-s3-c6-which-board-to-choose.html)
- [自作は既製品より安い？ 部品代の外にある費用](https://nodus-lab.pages.dev/articles/diy-or-ready-made-total-cost.html)
