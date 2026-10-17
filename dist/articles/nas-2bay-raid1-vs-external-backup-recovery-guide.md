# 初めての2ベイNAS、HDD 2台を「RAID 1」にするか「1台運用＋外付け・外部バックアップ」にするか

> 2ベイNASとHDD 2台を買うとき、RAID 1（ミラーリング）を組めばバックアップは不要なのか。防げる障害と防げない事故（誤削除・落雷・ランサムウェア）の境界を整理します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/nas-2bay-raid1-vs-external-backup-recovery-guide
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/nas-2bay-raid1-vs-external-backup-recovery-guide.csv
- **Category**: Hardware & Power Electronics
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- RAID 1（ミラーリング）は「片方のHDDが物理故障したときにサービスを止めない仕組み（冗長化）」であり、誤ってファイルを削除・上書きした瞬間にもう片方のHDDからも同時に消える。
- NAS本体の電源回路故障、落雷、水濡れ、ランサムウェア感染、ソフトウェアのバグによるデータ破損は、同じ筐体内のRAID 1では防げない。
- 予算がHDD 2台分に限られていて「家族の写真や重要書類を絶対に失いたくない」のが最優先なら、同じNAS内でRAID 1を組むより、別筐体（外付けHDDやクラウド）へ世代バックアップを残す方が守れる範囲が広い。


## 選択肢の比較表
| トラブルの種類 | 2ベイNAS単体のRAID 1（外付け・外部退避なし） | 1ベイ運用＋別ドライブ/クラウドへの世代バックアップ | 違いが生じる理由 |
| --- | --- | --- | --- |
| HDD 1台の突然の物理故障 | そのまま稼働継続（新しいHDDへ交換して再構築） | NASは停止するがバックアップからデータを復元可能 | ダウンタイム（停止時間）をゼロにしたいかどうか |
| 操作ミスによるファイル誤削除・上書き | 守れない（2台同時に即座に削除・上書きされる） | 過去世代のバックアップから復元可能 | リアルタイム同期と履歴保持（バージョニング）の差 |
| NAS本体の基板・電源故障や落下 | 本体修理・同系統機への移行が必要（同時破損リスクあり） | 別筐体やクラウドに独立したデータが残る | 同じ電源・同じケースに2台入っているか別場所か |
| ランサムウェアや同期ソフトの暴走 | 守れない（ミラー先も同時に暗号化・破壊される） | オフライン外付けHDDやImmutable保存なら復旧可能 | 常時同一ファイルシステムとして見えているかどうか |

## 詳細解説・原因分析
### RAID 1が守るのは「データそのもの」ではなく「HDD 1台故障時の稼働継続」
初めて2ベイNASを購入する際、「HDDを2台入れてRAID 1（ミラーリング）にしておけば、同じデータが2つ保存されるからバックアップは完璧だ」と誤解されがちです。しかしRAID 1の目的は「稼働の継続性（可用性）」にあります。2台のHDDにリアルタイムで全く同じ書き込みを行うため、1台のHDDが物理的に壊れても作業を止めずにファイルへアクセスし続けられます。その反面、自分が誤って大切な写真フォルダを消してしまったり、ファイルが壊れた状態で上書き保存されたりすると、その変更も0.1秒後にはもう片方のHDDへ忠実にミラーリングされます。
参照: [Immich Docs：Backup and Restore（3-2-1バックアップ戦略と世代保持）](https://immich.app/docs/administration/backup-and-restore/)

### 同じ筐体・同じ電源に入っている2台は同時にダメージを受けることがある
また、2ベイNASの中の2台のHDDは、同じ電源アダプター、同じ基板、同じ設置場所を共有しています。落雷や停電時のサージ電流、ペットや子どもによる本体の転倒、あるいは夏場のファン停止による高温状態が起きた場合、2台のHDDが同時に故障するリスクはゼロではありません。さらに同時期に同じロットで買った2台のHDDを同じ時間だけ回し続けると、1台目が壊れて新しいHDDと入れ替え、数時間〜十数時間かけて全領域を読み出す「リビルド（再構築）」の高負荷の最中に、寿命が近づいていた2台目まで壊れてしまうケースも考慮する必要があります。
参照: [Immich Docs：Backup and Restore（3-2-1バックアップ戦略と世代保持）](https://immich.app/docs/administration/backup-and-restore/)

### 予算がHDD 2台分なら「1台をNAS、もう1台を別系統の履歴バックアップ」にする選択肢
もし「自宅のNASが数時間〜1日止まること」よりも「撮りためた写真やデータが永久に消えること」の方が困るのであれば、Immichの公式ドキュメント等でも推奨されている「3-2-1バックアップ戦略（データを3つ持ち、2種類の媒体に分け、1つは別場所に置く）」に近づける方が安全です。予算がHDD 2台分しかない場合は、最初から2台とも同じNASに入れてRAID 1にするのではなく、1台をメインの保存先とし、もう1台は外付けUSBケースに入れて「夜間に自動で差分・世代バックアップを取る別ドライブ」にするか、あるいは特に重要な数百GB分だけをCloudflare R2やBackblaze B2などの安価なクラウドストレージへ暗号化バックアップする方が、誤削除にも本体故障にも対応できます。
参照: [Immich Docs：Backup and Restore（3-2-1バックアップ戦略と世代保持）](https://immich.app/docs/administration/backup-and-restore/)
参照: [Backblaze：B2 Cloud Storage Pricing](https://www.backblaze.com/cloud-storage/pricing)
参照: [Cloudflare R2 Docs：Pricing](https://developers.cloudflare.com/r2/pricing/)

### RAID 1を組む場合でも「外へのバックアップ」だけは必ず組み合わせる
もちろん、家族全員が毎日アクセスしていてHDD交換中もサーバーを止めたくないなら、2ベイNASでRAID 1を組むこと自体は非常に便利です。大切なのは「RAID 1にしたからバックアップは終わり」で止めないことです。RAID 1で日常のディスク故障による停止を防ぎつつ、本当に消えたら困るデータだけは外付けドライブや月数百円のクラウドストレージへ世代バックアップする2段構えにすることで、初めて安心して運用できます。
参照: [Immich Docs：Backup and Restore（3-2-1バックアップ戦略と世代保持）](https://immich.app/docs/administration/backup-and-restore/)
参照: [Backblaze：B2 Cloud Storage Pricing](https://www.backblaze.com/cloud-storage/pricing)
参照: [Cloudflare R2 Docs：Pricing](https://developers.cloudflare.com/r2/pricing/)

## 記事の範囲
2026年10月16日にImmich公式バックアップガイド（3-2-1ルール）およびクラウドストレージ料金資料を参照し、RAID 1（冗長化）とバックアップ（履歴・別筐体退避）の役割分担を整理した記事です。


## 参考資料
- [Immich Docs：Backup and Restore（3-2-1バックアップ戦略と世代保持）](https://immich.app/docs/administration/backup-and-restore/)
- [Backblaze：B2 Cloud Storage Pricing](https://www.backblaze.com/cloud-storage/pricing)
- [Cloudflare R2 Docs：Pricing](https://developers.cloudflare.com/r2/pricing/)

## 次に考えたいこと
- [Immichは写真フォルダだけコピーすれば戻せる？ データベースダンプと復元範囲の確認](https://nodus-lab.pages.dev/articles/immich-backup-photos-database-restore-scope)
- [安いクラウドバックアップで100GBを戻すといくら？ 保存料金と復元時の下り転送費用](https://nodus-lab.pages.dev/articles/cloud-backup-100gb-restore-egress-cost-comparison)
