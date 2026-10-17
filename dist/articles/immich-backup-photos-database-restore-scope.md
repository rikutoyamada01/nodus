# Immichは写真フォルダだけコピーすれば戻せる？ データベースダンプと復元範囲の確認

> 自宅で写真管理サーバーImmichを運用するとき、画像ファイル本体だけを別HDDへコピーしていてもアルバムやユーザー情報が戻らない理由と、公式のバックアップ・復元手順を整理します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/immich-backup-photos-database-restore-scope
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/immich-backup-photos-database-restore-scope.csv
- **Category**: Cloud & AI Infrastructure
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- Immichはファイルパスやユーザーのメタデータをデータベースで管理しており、後から写真の保存フォルダだけを置いても自動スキャンされないため、データベースのバックアップが不可欠である。
- 反対に、データベースの自動バックアップ（既定で毎日午前2時・直近14回分保持）には写真や動画の実体ファイルは含まれないため、両方をセットで保護する必要がある。
- 本番データが消える前に、UPLOAD_LOCATION内の画像ファイル群と backups フォルダ内のDBダンプ、および .env と docker-compose.yml を別ドライブや外部へ退避する仕組みを作る。


## 選択肢の比較表
| 保存対象 | 含まれる情報 | これだけを復元したときに起きること | 公式ドキュメント上の位置づけ |
| --- | --- | --- | --- |
| 写真・動画の実体ファイル群（UPLOAD_LOCATION） | アップロードされた元の画像・動画データ等 | Immichがフォルダを自動スキャンしないため画面に認識されない | DBダンプと組み合わせて外部へバックアップ必須 |
| データベースダンプ（UPLOAD_LOCATION/backups） | ファイルパス、ユーザー、アルバム等のメタデータ | メタデータだけで写真・動画ファイル本体が存在しないため表示不可 | 既定で毎日2:00に自動作成（14世代保持）されるが外部退避が必要 |
| 設定ファイル（.env / docker-compose.yml） | 保存先パス、DB接続情報、コンテナ構成 | 単体ではデータを持たないが新規環境での再構築手順で必要 | Onboardingからの復元時に最初に配置する |

## 詳細解説・原因分析
### 写真フォルダをコピーしただけではImmichの画面に元通り並ばない
自宅サーバーやNASでImmichを動かす際、「写真の保存先フォルダさえ外付けHDDにコピーしておけば、サーバーが壊れてもそのフォルダを指定し直せば元に戻るだろう」と考えがちです。しかし、2026年10月16日確認のImmich公式ドキュメント（Backup and Restore）には、「Immichはファイルパスとユーザーのメタデータをデータベースに保存する。ライブラリフォルダをスキャンする動作は行わないため、データベースのバックアップが不可欠である」と明記されています。つまり、データベースを失った状態で画像フォルダだけを新しいImmichにつないでも、作成済みのアルバムやユーザー紐づけ、登録状態はそのままでは復元されません。
参照: [Immich Docs：Backup and Restore](https://immich.app/docs/administration/backup-and-restore/)

### 自動作成されるDBダンプには写真ファイル本体が含まれない
Immichには障害復旧のための自動データベースバックアップ機能が備わっており、既定では毎日午前2時にダンプが作成され、`UPLOAD_LOCATION/backups` 内に直近14回分が保存されます（管理画面のDatabase Dump Settingsから変更可能）。ただし、公式ドキュメントで注意喚起されている通り、このデータベースバックアップにはメタデータしか入っておらず、写真や動画のファイル本体は一切含まれていません。また、`UPLOAD_LOCATION/backups` は写真と同じドライブ上にあるため、SSDやHDD自体が故障すると写真もDBダンプも同時に失われます。
参照: [Immich Docs：Backup and Restore](https://immich.app/docs/administration/backup-and-restore/)

### Immichの準備機能と外部へのコピー（3-2-1ルール）を分ける
公式ドキュメントでも冒頭で「このページの機能はImmichインスタンスをバックアップ可能な状態に整えるものであり、実際のバックアップツールを使って別場所へコピーする処理自体は利用者自身で行う必要がある」と強調され、3-2-1バックアップ戦略が推奨されています。具体的には、Immichが `UPLOAD_LOCATION/backups` に出力したデータベースダンプと、`UPLOAD_LOCATION` 内の元画像・動画フォルダ、そして構成ファイル（`.env` と `docker-compose.yml`）を、別ドライブや外部クラウドストレージへ定期的に退避させます。
参照: [Immich Docs：Backup and Restore](https://immich.app/docs/administration/backup-and-restore/)
参照: [Docker Docs：Bind mounts](https://docs.docker.com/engine/storage/bind-mounts/)

### Web画面からの復元機能と初期オンボーディング時の復元手順を確認する
データベースダンプと実体ファイルの両方が揃っていれば、復元はWebインターフェースまたはコマンドラインから行えます。公式ドキュメントでは、既存環境なら管理画面の「Administration > Maintenance」から利用可能なバックアップ一覧を選んで復元でき、実行前に自動でリストアポイント（ロールバック用）が作成される仕組みが説明されています。また、別マシンへ新規導入して初期画面（Onboarding）から復元する手順も用意されているため、写真データが数百GBに膨らむ前に、少量のテスト画像を入れた状態で一度「バックアップからの復元」を実際に試しておくと安心です。
参照: [Immich Docs：Backup and Restore](https://immich.app/docs/administration/backup-and-restore/)

## 記事の範囲
2026年10月16日にImmich公式ドキュメント（Backup and Restore）およびDocker公式ドキュメントを確認して整理した記事です。特定のNASやストレージ環境における復元所要時間の実測は行っていません。


## 参考資料
- [Immich Docs：Backup and Restore](https://immich.app/docs/administration/backup-and-restore/)
- [Docker Docs：Bind mounts](https://docs.docker.com/engine/storage/bind-mounts/)

## 次に考えたいこと
- [安いクラウドバックアップで100GBを戻すといくら？ 保存料金と下り転送費用の比較](https://nodus-lab.pages.dev/articles/cloud-backup-100gb-restore-egress-cost-comparison)
- [パーソナルAIを24時間動かすなら、ラズパイ・VPS・ミニPCのどれ？](https://nodus-lab.pages.dev/articles/always-on-personal-ai-raspberry-pi-vps-mini-pc)
