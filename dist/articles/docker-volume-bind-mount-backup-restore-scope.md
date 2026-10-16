# Dockerの作業フォルダをコピーしたのに復元できない理由：VolumeとBind Mountの保存範囲

> docker-compose.ymlがあるフォルダを丸ごとバックアップしたのに、別マシンへ移したらデータベースの中身が空になっていた。名前付きVolumeとBind Mountの保存場所の違いを整理します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/docker-volume-bind-mount-backup-restore-scope.html
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/docker-volume-bind-mount-backup-restore-scope.csv
- **Category**: Cloud & AI Infrastructure
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- Dockerのデータ永続化には「Volumes（Docker管理領域に保存）」と「Bind mounts（ホストの任意パスを共有）」があり、作業フォルダのコピーだけで移せるのはカレントディレクトリ配下のBind mountのみである。
- docker-compose.ymlで `db_data:/var/lib/postgresql/data` のように名前付きVolumeを使っている場合、実データはDocker管理領域（`/var/lib/docker/volumes/` 等）にあるためプロジェクトフォルダをコピーしても含まれない。
- 稼働中のデータベースファイルを生のままコピーすると破損するリスクがあるため、DBは公式のダンプ出力（pg_dump等）を保存し、静的ファイルと一緒に退避させる。


## 選択肢の比較表
| マウント方式（記述例） | ホスト上の実際の保存場所 | 作業フォルダのコピーに含まれるか | バックアップ時の注意点 |
| --- | --- | --- | --- |
| 相対パスのBind mount（./data:/app/data） | 作業フォルダ直下の ./data ディレクトリ | 含まれる | 権限（UID/GID）や稼働中DBの書き込み競合に注意 |
| 絶対パスのBind mount（/mnt/nas/photos:/photos） | 指定した外部パス（/mnt/nas/photos） | 作業フォルダには含まれない（別パス） | マウント先ドライブも含めてバックアップ対象に指定する |
| 名前付きVolume（db_data:/var/lib/postgresql/data） | Docker Engine管理領域（/var/lib/docker/volumes/等） | 含まれない（最も見落としやすい） | docker volume用の退避手順またはDBダンプ出力が必要 |

## 詳細解説・原因分析
### docker-compose.ymlがあるフォルダをコピーしても名前付きVolumeは付いてこない
ミニPCの買い替えやサーバー移行の際、`docker-compose.yml` が置かれている作業フォルダを丸ごと圧縮して新しいマシンへコピーしたのに、起動すると初期状態（データが空）に戻ってしまうトラブルがよく起きます。原因の多くは、`volumes:` 欄の書き方の違いにあります。`./config:/config` のように `./` や `/` から始まるパスを指定した場合は「Bind mount（バインドマウント）」となり、そのフォルダ内にファイルが保存されます。一方、`db_data:/var/lib/mysql` のようにパスではなく名前だけを指定した場合は「名前付きVolume（Named Volume）」となり、実データは作業フォルダの外にあるDocker専用の管理ディレクトリ内に保存されるため、作業フォルダだけをコピーしてもデータは1バイトも含まれません。
参照: [Docker Docs：Volumes](https://docs.docker.com/engine/storage/volumes/)
参照: [Docker Docs：Bind mounts](https://docs.docker.com/engine/storage/bind-mounts/)

### ホスト側のファイルを直接書き換えられるBind mountの特徴とリスク
Docker公式ドキュメント（Bind mounts）で説明されている通り、Bind mountはホストマシン上のファイルやディレクトリをそのままコンテナ内へマウントする仕組みです。ホスト側のバックアップツールから直接ファイルを見られるため個人サーバーでは管理しやすい反面、コンテナ内のプロセスからもホスト上のファイルを作成・変更・削除できる（既定で書き込み可能）という特徴があります。設定ファイルなどコンテナ側から書き換える必要がないものは `:ro`（読み取り専用）を付けてマウントすることで、意図しない上書きや破損を防げます。
参照: [Docker Docs：Bind mounts](https://docs.docker.com/engine/storage/bind-mounts/)

### データベースの保存領域は稼働中にそのままファイルコピーしない
ではすべてを `./db:/var/lib/postgresql/data` のようなBind mountに統一して毎日フォルダごとコピーすれば安全かというと、データベースに関しては別の注意が必要です。PostgreSQLやMySQL、SQLiteなどが稼働して書き込みを行っている最中に外からデータファイルを直接コピーすると、メモリ上の未反映データとディスク上のファイルが食い違い、復元時にデータベースが破損して起動しなくなることがあります。Immichの公式バックアップドキュメントでも、写真ファイル本体はフォルダコピーで保護しつつ、データベースについては専用の作成ジョブ（DBダンプ出力）を使って整合性の取れたダンプファイルを作成・保存する手順が採られています。
参照: [Docker Docs：Volumes](https://docs.docker.com/engine/storage/volumes/)
参照: [Immich Docs：Backup and Restore](https://immich.app/docs/administration/backup-and-restore/)

### 移行前に docker compose config と volume 一覧で保存先を棚卸しする
自宅サーバーのバックアップを設定する際は、まず各コンテナの `docker-compose.yml` と `.env` ファイルを見直し、どのデータが「相対パスのBind mount」「別ドライブの絶対パス」「名前付きVolume」のどれに入っているかを書き出します。その上で、一度別ディレクトリやテスト環境でバックアップファイルだけからコンテナを起動し、ログイン情報や過去データが本当に復元できるかを試しておくことが最も確実な保険になります。
参照: [Docker Docs：Volumes](https://docs.docker.com/engine/storage/volumes/)
参照: [Docker Docs：Bind mounts](https://docs.docker.com/engine/storage/bind-mounts/)
参照: [Immich Docs：Backup and Restore](https://immich.app/docs/administration/backup-and-restore/)

## 記事の範囲
2026年10月16日にDocker公式ドキュメント（Volumes、Bind mounts）およびImmich公式バックアップガイドを確認して整理した記事です。


## 参考資料
- [Docker Docs：Volumes](https://docs.docker.com/engine/storage/volumes/)
- [Docker Docs：Bind mounts](https://docs.docker.com/engine/storage/bind-mounts/)
- [Immich Docs：Backup and Restore](https://immich.app/docs/administration/backup-and-restore/)

## 次に考えたいこと
- [Immichは写真フォルダだけコピーすれば戻せる？ データベースダンプと復元範囲の確認](https://nodus-lab.pages.dev/articles/immich-backup-photos-database-restore-scope.html)
- [パーソナルAIを24時間動かすなら、ラズパイ・VPS・ミニPCのどれ？](https://nodus-lab.pages.dev/articles/always-on-personal-ai-raspberry-pi-vps-mini-pc.html)
