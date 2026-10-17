# NASにTailscaleを入れられないとき、Subnet RouterとExit Nodeのどちらを使うか

> アプリを追加できないNASやプリンターへ外出先から接続したいとき、宅内の特定機器だけを通す構成と全通信を自宅経由にする構成の違いを公式資料から整理します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/tailscale-subnet-router-vs-exit-node-nas-guide
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/tailscale-subnet-router-vs-exit-node-nas-guide.csv
- **Category**: Cloud & AI Infrastructure
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- 自宅のNASやプリンターなど特定のローカルIP機器にだけ外出先からアクセスしたいなら、Subnet Router（サブネットルーター）を選ぶ。
- 外出先の公衆Wi-Fi利用時などに、一般のWeb閲覧を含むすべてのインターネット通信を自宅回線経由にしたい場合はExit Node（出口ノード）を使う。
- 公式資料では、Subnet Routerの背後にある非Tailscale機器はプランのデバイス数上限にカウントされないと明記されている。


## 選択肢の比較表
| 機能名 | 転送される通信の範囲 | 適している用途 | プラン上限・運用上の特徴 |
| --- | --- | --- | --- |
| 各端末へ直接導入 | Tailscale導入済みの端末同士のみ | PC・スマホ・対応NAS間の最も基本的な通信 | 端末ごとにエンドツーエンド暗号化・最良の性能 |
| Subnet Router | 指定したローカルサブネット（例：192.168.1.0/24）宛てのみ | アプリを入れられないNAS、プリンター、ルーター管理画面への接続 | 背後の機器はプランのデバイス数上限に非計上 |
| Exit Node | 一般サイト閲覧を含むすべてのインターネット通信（0.0.0.0/0） | 公衆Wi-Fiでの通信保護、海外から日本国内向けサービスへの接続 | 普段のWeb通信もすべて中継器を通るため帯域を消費 |

## 詳細解説・原因分析
### 自宅のNASやプリンターへつなぐ目的ならSubnet Routerが基本になる
専用アプリを追加できないエントリーモデルのNASやネットワークプリンター、スマートホーム機器に外出先からアクセスしたい場合、必要になるのは「Subnet Router（サブネットルーター）」です。公式ドキュメントによると、Subnet RouterはTailscaleネットワーク（tailnet）と物理的なローカルサブネットの間をつなぐゲートウェイとして機能します。自宅内で常時稼働しているラズパイやミニPC 1台にTailscaleを入れてSubnet Routerに設定すれば、外出先のスマホやPCから自宅LAN内の特定IPアドレスへそのままアクセスできるようになります。
参照: [Tailscale Docs：Subnet routers（サブネットルーターの仕組みと制限）](https://tailscale.com/docs/features/subnet-routers)

### Exit Nodeは一般のWeb閲覧を含むすべての通信を自宅経由に変える
一方、「Exit Node（出口ノード）」は目的が異なります。通常、Tailscaleはtailnet内の機器宛ての通信だけを通し、GoogleやSNSなどの一般サイトを見る通信には関与しません（オーバーレイネットワーク）。しかしExit Nodeを有効にすると、デフォルトルート（`0.0.0.0/0` および `::/0`）が書き換わり、すべてのインターネット通信がそのExit Nodeを経由して外へ出るようになります。カフェの信頼できないWi-Fiを使うときや、海外旅行中に自宅のIPアドレス経由で国内限定サービスへアクセスしたいときには便利ですが、単に自宅NASのファイルを開きたいだけの用途で常時ONにすると、無関係な動画視聴などの通信まで自宅回線を経由してしまいます。
参照: [Tailscale Docs：Exit nodes (route all traffic)](https://tailscale.com/kb/1103/exit-nodes)

### Subnet Routerの背後にある機器はデバイス数上限を消費しない
個人プランやチームプランで気になるのが登録できるデバイス数の上限ですが、公式ドキュメント（Subnet routers）には「Subnet Routerの背後にあるデバイスは、料金プランのデバイス数上限にはカウントされない」と明記されています。たとえば自宅にNAS、ネットワークカメラ、プリンター、センサーなど10台の機器があっても、中継役となる1台のSubnet RouterだけをTailscaleに登録すれば、デバイス枠を1台分しか使わずにサブネット内の対象機器へ到達できます。
参照: [Tailscale Docs：Subnet routers（サブネットルーターの仕組みと制限）](https://tailscale.com/docs/features/subnet-routers)
参照: [Tailscale：Pricing](https://tailscale.com/pricing)

### 中継役にする機器の電源維持とアクセス制御の範囲を決める
Subnet RouterもExit Nodeも、中継役に指定した宅内機器の電源が落ちていたりスリープに入っていたりすると外出先から接続できなくなります。そのため、普段持ち歩くノートPCではなく、常時稼働しているミニPCやRaspberry Piなどを割り当てるのが適しています。また、Subnet Routerを使う場合は宅内LANと中継機器の間は通常のLAN通信になるため、不要な機器まで広く公開しすぎないようサブネットの範囲やアクセス制御ポリシー（ACL）を絞って運用します。
参照: [Tailscale Docs：Subnet routers（サブネットルーターの仕組みと制限）](https://tailscale.com/docs/features/subnet-routers)
参照: [Tailscale Docs：Exit nodes (route all traffic)](https://tailscale.com/kb/1103/exit-nodes)

## 記事の範囲
2026年10月16日にTailscale公式ドキュメント（Subnet routers、Exit nodes）およびPricingページを確認して整理した記事です。特定のルーターやNAS機種でのスループット測定は行っていません。


## 参考資料
- [Tailscale Docs：Subnet routers（サブネットルーターの仕組みと制限）](https://tailscale.com/docs/features/subnet-routers)
- [Tailscale Docs：Exit nodes (route all traffic)](https://tailscale.com/kb/1103/exit-nodes)
- [Tailscale：Pricing](https://tailscale.com/pricing)

## 次に考えたいこと
- [Tailscaleで外出先からのNAS転送が遅いとき、回線変更の前に直結とDERP中継を確認する](https://nodus-lab.pages.dev/articles/tailscale-nas-slow-direct-derp-relay-check)
- [パーソナルAIを24時間動かすなら、ラズパイ・VPS・ミニPCのどれ？](https://nodus-lab.pages.dev/articles/always-on-personal-ai-raspberry-pi-vps-mini-pc)
