# Tailscaleで外出先からのNAS転送が遅いとき、回線変更の前に直結とDERP中継を確認する

> 自宅NASやサーバーへのリモート接続が期待より遅いとき、光回線やルーターを疑う前に確認したい3つの接続方式（Direct / DERP / Peer Relay）の切り分け手順です。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/tailscale-nas-slow-direct-derp-relay-check.html
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/tailscale-nas-slow-direct-derp-relay-check.csv
- **Category**: Cloud & AI Infrastructure
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- Tailscaleの通信経路にはUDP直結（Direct）、DERPサーバー中継、Tailscale Peer Relay中継の3種類があり、いずれもWireGuardで暗号化されているが性能が大きく異なる。
- NAT越えに失敗してDERP中継（フォールバック）になっている場合、自宅の光回線やNASを高速なものに変えても中継経路上の上限がボトルネックになりやすい。
- 機器や回線を買い替える前に、現在の通信がDirect接続になっているか、外出先のWi-FiやファイアウォールがUDP通信を妨げていないかを切り分ける。


## 選択肢の比較表
| Tailscaleの接続方式 | 通信の経路 | 性能の特徴（公式説明） | 遅いときに確認すること |
| --- | --- | --- | --- |
| Direct connections（直結） | 端末間でUDPパケットを直接送受信（NAT越え成功後） | 最も低遅延かつ高スループットが出やすい | 外出先モバイル回線や自宅上り回線そのものの速度 |
| DERP relayed connections | Tailscale提供のDERPサーバーを中継して送受信 | 直結不可時のフォールバック。セキュリティは同等だが速度・遅延面で不利 | 両端のNAT種別、UDPポート遮断、キャリアグレードNAT等の影響 |
| Tailscale Peer Relay | 同一tailnet内の別端末を中継役にして送受信 | 直接つながらない端末間を自前の別ノード経由で橋渡しする | 中継役にした端末の回線帯域と負荷 |

## 詳細解説・原因分析
### 暗号化の安全性は同じでも直結と中継では転送性能が大きく変わる
Tailscale公式ドキュメント（Connection types）によると、tailnet内の端末間通信には「Direct connections（UDPによる直接通信）」「DERP relayed connections（DERPサーバー経由の中継通信）」「Tailscale Peer Relay connections（同一tailnet内の別端末経由の中継通信）」の3種類があります。いずれの方式もWireGuardによってエンドツーエンドで暗号化されており、安全性に違いはありません。しかし性能面では、Direct接続が最も低遅延・高スループットであるのに対し、DERP中継は直接通信が確立できない場合のフォールバック（代替経路）として動作するため、大きなファイルのNAS転送では速度差が顕著に表れます。
参照: [Tailscale Docs：Connection types（Direct / DERP / Peer Relayの仕組み）](https://tailscale.com/kb/1257/connection-types)

### 最初の中継から直結への切り替え（NAT越え）が成功しているかを見る
公式資料で説明されている接続手順では、2台の端末は最初から直接通信するわけではありません。まず最寄りのDERPサーバーを通じて接続要求と直結用の経路情報を交換し、その後に双方がNAT越え（NAT traversal）を試みてUDP直結へ移行します。もしカフェの公衆Wi-Fi、ホテルや職場の厳しいファイアウォール、あるいは特定のモバイル回線環境でUDP通信やNAT越えが阻まれると、通信は切断されずにそのままDERP中継で維持されます。「つながるのに極端に遅い」という現象の多くは、このフォールバック状態のままファイル転送を行っているケースです。
参照: [Tailscale Docs：Connection types（Direct / DERP / Peer Relayの仕組み）](https://tailscale.com/kb/1257/connection-types)

### 自宅の回線やNASを疑う前に3つのステップで原因を切り分ける
外出先からのNASアクセスが遅いときは、機器の買い替えや回線変更を検討する前に以下の順番で原因を切り分けます。
1. 自宅の同じLAN内でNASへ直接アクセスし、NAS自体や宅内LANの速度に問題がないか確かめる。
2. 外出先から接続した状態で、Tailscaleのステータス表示（`tailscale status` や `tailscale ping` 等）を確認し、通信経路が直結（direct）になっているか中継（relay / DERP）になっているかを確かめる。
3. もし中継になっている場合は、外出先のWi-Fiからスマートフォンのテザリング等へ一時的に切り替えて再接続し、外出先ネットワーク側のUDP制限が原因かどうかを確認する。
参照: [Tailscale Docs：Connection types（Direct / DERP / Peer Relayの仕組み）](https://tailscale.com/kb/1257/connection-types)
参照: [Tailscale Docs：Subnet routers](https://tailscale.com/docs/features/subnet-routers)

### 直結できているのに遅い場合は自宅の「上り回線速度」と中継機器を確認する
確認の結果、Direct接続になっているにもかかわらず転送が遅い場合は、自宅インターネット回線の「上り（アップロード）実効速度」または外出先回線の「下り速度」のどちらか遅い方が上限になっています。また、NAS本体にTailscaleを入れられず、ラズパイ等の小型機器をSubnet Router（サブネットルーター）として挟んでいる場合は、その中継機器の有線/無線LAN速度やCPU負荷がボトルネックになっていないかも併せて確認します。
参照: [Tailscale Docs：Connection types（Direct / DERP / Peer Relayの仕組み）](https://tailscale.com/kb/1257/connection-types)
参照: [Tailscale Docs：Subnet routers](https://tailscale.com/docs/features/subnet-routers)

## 記事の範囲
2026年10月16日にTailscale公式ドキュメント（Connection types、Subnet routers）を確認して整理した記事です。特定のISPやモバイル回線における実測スループットやレイテンシの測定は行っていません。


## 参考資料
- [Tailscale Docs：Connection types（Direct / DERP / Peer Relayの仕組み）](https://tailscale.com/kb/1257/connection-types)
- [Tailscale Docs：Subnet routers](https://tailscale.com/docs/features/subnet-routers)

## 次に考えたいこと
- [パーソナルAIを24時間動かすなら、ラズパイ・VPS・ミニPCのどれ？](https://nodus-lab.pages.dev/articles/always-on-personal-ai-raspberry-pi-vps-mini-pc.html)
- [Wi-Fi 7ルーター、買い替える前に確認すること](https://nodus-lab.pages.dev/articles/wifi7-routers-6ghz-mlo-real-world-throughput-wall-attenuation.html)
