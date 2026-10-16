# 家族だけに自宅アプリを見せたいとき、VPN（Tailscale）とCloudflare Tunnelで何が変わる？

> 自宅サーバーで動かしている写真管理やスマートホーム画面を外出先や家族のスマホから開きたいとき、全端末にVPNアプリを入れる構成とブラウザだけで開ける構成の違いを整理します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/home-server-access-vpn-vs-cloudflare-tunnel-guide.html
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/home-server-access-vpn-vs-cloudflare-tunnel-guide.csv
- **Category**: Cloud & AI Infrastructure
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- 両方式とも自宅ルーターのポート開放（インバウンド穴あけ）を行わずに外出先から自宅サーバーへ接続できるが、使う側の端末に必要な準備と通信経路が異なる。
- Tailscaleは利用する家族全員のスマホ・PCへ専用アプリの導入とログインが必要になる一方、端末間でWireGuardによる直接暗号化通信（UDP直結等）が行われる。
- Cloudflare Tunnelは自宅側で cloudflared デーモンを動かせば、家族側は専用VPNアプリを入れなくても通常のブラウザURLとCloudflare Access認証だけで開けるが、通信は必ずCloudflareのネットワークを経由する。


## 選択肢の比較表
| 比較項目 | プライベートVPN（Tailscale等） | Cloudflare Tunnel（cloudflared） | 判断の分かれ目 |
| --- | --- | --- | --- |
| 使う人（家族）の端末準備 | 全員のスマホ・PCに専用アプリ導入と常時ONが必要 | 専用VPNアプリ不要（標準ブラウザからURLを開く） | 家族の端末にVPNアプリを入れて管理できるか |
| 自宅ルーターのポート開放 | 不要（NAT越えまたはDERP中継） | 不要（cloudflaredからのアウトバウンド接続のみ） | どちらも固定IPやルーターのポート開放は不要 |
| 通信の通り道 | 端末間の直接暗号化通信（直結不可時は中継） | すべての通信がCloudflareのエッジネットワークを経由 | 大容量ファイル転送かWeb画面の閲覧中心か |
| 未認証アクセスの遮断位置 | tailnet外の端末からはポート自体が見えない | URL自体は公開到達可能になるためAccess等の前段認証が必須 | ログイン画面をインターネット側へ出すか |

## 詳細解説・原因分析
### どちらもルーターのポート開放は不要だが接続の向きと通り道が異なる
従来、自宅サーバーへ外からアクセスするには自宅ルーターのポートを開放する必要がありましたが、TailscaleとCloudflare Tunnelはいずれもルーターのインバウンドポートを開けずに導入できます。Cloudflare Tunnelの公式ドキュメントによると、自宅サーバー上で動く軽量デーモン（`cloudflared`）がCloudflareのグローバルネットワークへ向けて外向き（アウトバウンド専用）の接続を張り、そこを通じてリクエストを受け取ります。一方、Tailscaleは接続元と自宅サーバーの双方にクライアントを入れ、WireGuardで暗号化された仮想ネットワーク（tailnet）内で直接または中継通信を行います。
参照: [Cloudflare One Docs：Cloudflare Tunnel (Connect private networks)](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
参照: [Tailscale Docs：Connection types](https://tailscale.com/kb/1257/connection-types)

### 家族のスマホにVPNアプリを入れ続けられるかが最初の判断基準になる
自分1人だけが使うならTailscaleを入れておくだけで完結しますが、ITに詳しくない家族と共有する場合は「クライアントアプリの管理負担」が大きな差になります。Tailscaleでは家族それぞれのスマホにアプリを入れ、電池節約機能等でVPNが切れていたらONにし直す操作が必要です。これに対しCloudflare Tunnelで独自ドメインのURLを発行すれば、家族は普段のSafariやChromeのブックマークから開くだけでアクセスできます。
参照: [Cloudflare One Docs：Cloudflare Tunnel (Connect private networks)](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
参照: [Tailscale Docs：Connection types](https://tailscale.com/kb/1257/connection-types)
参照: [Tailscale：Pricing](https://tailscale.com/pricing)

### Cloudflare Tunnelを使う場合はアプリ単体のログイン画面だけに頼らない
Cloudflare Tunnelで公開したURLは、設定した瞬間からインターネット上の誰でも到達できる状態になります。もし自作アプリやオープンソースツールのログイン画面をそのまま露出させると、パスワード総当たり攻撃やアプリ側の脆弱性を直接突かれるリスクが生じます。そのため、家族だけに限定して見せたい場合は、トンネルのすぐ前段にCloudflare Access（Zero TrustのメールワンタイムPINやGoogleアカウント認証など）を置き、許可したメールアドレスの家族以外はアプリのログイン画面自体に到達できない構成にするのが安全です。
参照: [Cloudflare One Docs：Cloudflare Tunnel (Connect private networks)](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)

### SMBファイル共有や大容量動画の転送ならVPN直結の方が向いている
Webブラウザで完結するダッシュボードやメモアプリの共有にはCloudflare Tunnelが便利ですが、WindowsのエクスプローラーやMacのFinderからNASの共有フォルダ（SMB）を直接マウントしたい場合や、何十GBもある動画ファイルを高速にコピーしたい場合は、端末間でUDP直結（Direct connection）ができるTailscaleの方が適しています。用途が「ブラウザ画面の共有」なのか「NASのファイル転送やSSH開発」なのかによって使い分けるか、自分用はTailscale・家族用のWeb画面だけCloudflare Tunnel（Access保護付き）と併用するのが現実的です。
参照: [Cloudflare One Docs：Cloudflare Tunnel (Connect private networks)](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
参照: [Tailscale Docs：Connection types](https://tailscale.com/kb/1257/connection-types)

## 記事の範囲
2026年10月16日にCloudflare One公式ドキュメント（Cloudflare Tunnel）およびTailscale公式ドキュメント（Connection types、Pricing）を確認して整理した記事です。


## 参考資料
- [Cloudflare One Docs：Cloudflare Tunnel (Connect private networks)](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
- [Tailscale Docs：Connection types](https://tailscale.com/kb/1257/connection-types)
- [Tailscale：Pricing](https://tailscale.com/pricing)

## 次に考えたいこと
- [Tailscaleで外出先からのNAS転送が遅いとき、回線変更の前に直結とDERP中継を確認する](https://nodus-lab.pages.dev/articles/tailscale-nas-slow-direct-derp-relay-check.html)
- [NASにTailscaleを入れられないとき、Subnet RouterとExit Nodeのどちらを使うか](https://nodus-lab.pages.dev/articles/tailscale-subnet-router-vs-exit-node-nas-guide.html)
