# Gemini 4 ArgonはProで使える？ Ultra限定の範囲を確認

> Google AI Proを契約している人へ。GeminiアプリとAntigravityの提供条件、Ultraへの追加費用、公開評価から分かる得意分野を整理します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/gemini-4-argon-google-ai-pro-ultra.html
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/gemini-4-argon-google-ai-pro-ultra.csv
- **Category**: Cloud & AI Infrastructure
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-14

## 選び方の要点
- Google AI ProでもGeminiアプリのArgonは提供対象。アプリで試すためだけにUltraへ変更する必要はありません。
- 独立したAntigravityデスクトップアプリ・CLIのArgonは、個人サブスクではUltra向け。ProのAntigravity利用特典とは区別します。
- 日本向け月額表示はPro 2,900円、Ultra 14,500円から。最小構成でも月11,600円の差があるため、使いたい場所と不足している利用枠から判断します。


## 選択肢の比較表
| Argonを使う場所 | Google AI Pro | Google AI Ultra | 確認する条件 |
| --- | --- | --- | --- |
| Geminiアプリ | 提供対象 | 提供対象 | 対象国・アカウント条件・順次提供 |
| Google検索のAIモード | 提供対象（地域等の条件あり） | 提供対象（地域等の条件あり） | 検索のAIモード固有の地域・言語条件 |
| 独立したAntigravityアプリ・CLI | Argonのサブスク提供対象として記載なし | 個人サブスクの提供対象 | Antigravity自体へのアクセスとArgonへのアクセスは別 |
| Gemini API | 有料APIを別途利用 | サブスク特典と従量課金を区別 | APIの課金設定・利用枠を確認 |

## 詳細解説・原因分析
### Pro契約者は、まずGeminiアプリで使える範囲を確認する
Google AI Proを使っているなら、Argonを試す入口はGeminiアプリです。日本向けの公式プラン表でもProの対象モデルにArgonが含まれています。今の契約を継続して使う範囲なら、Argon用に別の上位契約を結ぶ必要はありません。Google Oneの保存容量だけの契約や、名前の似たGoogle AI PlusはProと別です。まずGoogle Oneでプラン名とログイン中のアカウントを確認してください。
参照: [Google One：日本向けGoogle AIプラン表](https://one.google.com/intl/ja_jp/about/google-ai-plans/)
参照: [Gemini：日本向けサブスクリプション料金](https://gemini.google/jp/subscriptions/?hl=ja)

### Ultra向けなのは、AntigravityでのArgon利用
Googleの発表では、独立したAntigravityデスクトップアプリとCLIでArgonを利用できる個人サブスクはGoogle AI Ultraです。ProにもAntigravityの特典はありますが、それだけでArgonを選べるとは限りません。Geminiアプリでコードを相談することと、Antigravityからプロジェクトのファイルや開発ツールを操作させることは、契約上も使い方も異なります。Ultra契約者はAntigravityを最新版に更新し、モデルの提供状況を確認しましょう。
参照: [Google：Gemini 4 Argonの提供開始告知](https://blog.google/intl/en-in/products/introducing-gemini-4-argon/)
参照: [Antigravity：Argonのアプリ・CLI提供条件](https://antigravity.google/blog/gemini-4-argon-in-google-antigravity)

### Ultraへの追加費用は、最小構成でも月11,600円
Googleの日本向け月額表示はProが2,900円、Ultraが14,500円からで、32,000円の構成もあります。Proとの差額はそれぞれ月11,600円と29,100円。これは月額表示同士の計算で、契約変更日に請求される精算額ではありません。割引終了後や年払い・通信会社経由の契約では、自分の更新料金で比べてください。アプリのArgon利用だけが目的ならProがすでに対象なので、追加費用の理由はAntigravityでの利用や必要な利用枠にあるかを確認します。
参照: [Gemini：日本向けサブスクリプション料金](https://gemini.google/jp/subscriptions/?hl=ja)
参照: [Antigravity：Argonのアプリ・CLI提供条件](https://antigravity.google/blog/gemini-4-argon-in-google-antigravity)

### 追加料金に見合うだけの作業時間を短縮できるか
仮に自分の作業時間を1時間3,000円と評価すると、月11,600円の追加費用に見合う時短は約3.9時間、29,100円なら約9.7時間です。これは賃金や実測効果ではなく、差額を時間に置き換えた判断例です。Proで同じ仕事をした場合との差を測り、回答の確認、修正、上限待ちまで含めて時間が減るかを見ます。すでにUltraを契約している人は、この差額を新たな負担と考える必要はありません。今の枠で終わらせられる仕事を確認するのが先です。
参照: [Gemini：日本向けサブスクリプション料金](https://gemini.google/jp/subscriptions/?hl=ja)

### 利用枠は、固定の質問回数として読まない
英語版の公式ヘルプでは、Geminiアプリの使用量は質問の複雑さ、モデルや機能、会話の長さに依存し、5時間ごとの更新に加えて週間上限があると説明されています。短い質問と長い資料の分析を同じ1回として比べることはできません。確認時にはUltraの倍率が日本語ヘルプでProの4倍または20倍、英語版と日本向け料金ページで5倍または20倍と食い違っていました。倍率をArgonの保証回数には換算せず、Geminiの設定にある使用量上限と更新時刻を確認してください。このヘルプはGeminiアプリの説明であり、Antigravityの利用枠も同じ条件とは限りません。
参照: [Gemini：日本向けサブスクリプション料金](https://gemini.google/jp/subscriptions/?hl=ja)
参照: [Geminiヘルプ：使用量上限（英語版）](https://support.google.com/gemini/answer/16275805?hl=en)
参照: [Geminiヘルプ：使用量上限（日本語版）](https://support.google.com/gemini/answer/16275805?hl=ja)

### 長い資料の処理は、公開評価でも強みが見える
Googleの公開表では、長文の関係をたどるGraphWalksの256k〜1Mトークン区間でArgonのF1は84.2%、比較先の最高値は71.8%で、差は12.4ポイントでした。業務自動化のAutomationBenchも51.3%対42.5%で8.8ポイント上回っています。複数資料の情報整理や段階の多い作業を試す根拠にはなりますが、これらは日本語の会話満足度や日常作業の時短率ではありません。公開表には旧Geminiとの同条件比較がそろっていないため、普段使っていたモデルから何%改善するかは断定しません。
参照: [Google DeepMind：Argonの公開性能比較](https://deepmind.google/models/gemini/)
参照: [Google DeepMind：Argon評価方法](https://deepmind.google/models/evals-methodology/gemini-4-argon)

### コーディングの数値だけでUltraを選ばない
同じ公開表でも、ソフトウェア修正のDeepSWE v1.1はArgon 77.9%、比較先の最高値74.2%ですが、FrontierSWE v2は55.0%対65.5%で逆転します。さらにDeepSWEはArgonの自社測定と競合の公開値が混在しています。第三者のArtificial AnalysisではArgon highの総合指数は53、確認時の掲載順位は216モデル中8位でした。指数は正答率ではありません。上位のモデルであることと、自分の開発環境で追加料金分の仕事が進むことは、別に確かめる必要があります。
参照: [Google DeepMind：Argonの公開性能比較](https://deepmind.google/models/gemini/)
参照: [Google DeepMind：Argon評価方法](https://deepmind.google/models/evals-methodology/gemini-4-argon)
参照: [Artificial Analysis：Gemini 4 Argon high](https://artificialanalysis.ai/models/gemini-4-argon)

### 100万トークンの仕様と、サブスクの使用量を区別する
Gemini APIのArgon仕様は、入力と出力を合わせて1,048,576トークン。通常の同期出力の上限は65,536トークンで、最大約100万トークンの出力にはlong decodeの仕組みを使います。これはAPIの仕様で、GeminiアプリやAntigravityで毎回同じ長さを出せるという保証ではありません。一度に扱える情報量と、一定期間に使える計算量も別の制限です。長い資料が入るから使い放題、という理解では利用枠を見積もれません。
参照: [Google AI for Developers：ArgonのAPI仕様](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon)

### APIの発売価格は、サブスクの値下げではない
有料Gemini APIはサブスクとは別の利用経路です。Standardの100万トークン当たり料金は2026年11月30日まで入力2ドル・出力10ドル、12月1日以降は入力4ドル・出力20ドル。出力には思考トークンを含みます。この料金変更をProやUltraの月額変更と混同しないでください。アプリで対話したい既存Pro利用者が、ArgonのためにAPI課金を設定する必要はありません。独自ツールから使う場合は、サブスクの利用枠と分けて費用を管理します。
参照: [Google AI for Developers：API料金](https://ai.google.dev/gemini-api/docs/pricing)

### 使えないときは、契約・利用場所・提供条件の順で確認する
まずGoogle AI ProかUltraか、対象の個人アカウントでログインしているかを確認します。次にGeminiアプリなのか独立したAntigravityなのかを確認してください。Googleは順次提供と案内しており、日本向けプラン表も対象国や年齢などの条件を示しています。検索のAIモードにも固有の条件があります。日本でProやUltraを契約できても、すべての機能が同時に使えるとは限りません。表示されない理由を確かめる前に、上位プランへの変更だけで解決すると考えないことが大切です。
参照: [Google One：日本向けGoogle AIプラン表](https://one.google.com/intl/ja_jp/about/google-ai-plans/)
参照: [Google：Gemini 4 Argonの提供開始告知](https://blog.google/intl/en-in/products/introducing-gemini-4-argon/)
参照: [Geminiヘルプ：使用量上限（日本語版）](https://support.google.com/gemini/answer/16275805?hl=ja)

## 記事の範囲
2026年10月14日時点の公式プラン表、提供開始告知、ヘルプ、公開ベンチマークを参照した編集記事です。Nodusによる契約画面での動作確認、性能・利用枠の独自実測は行っていません。料金はGoogleの日本向け月額表示、差額と必要時短時間はその表示からの計算です。割引、年払い、通信会社経由の契約、変更時の精算は含めません。ベンチマークはAPI等での公開評価であり、サブスク画面で同じ結果や利用量を保証するものではありません。一般ユーザーの初期感想は性能・利用上限の根拠に採用していません。


## 参考資料
- [Google One：日本向けGoogle AIプラン表](https://one.google.com/intl/ja_jp/about/google-ai-plans/)
- [Gemini：日本向けサブスクリプション料金](https://gemini.google/jp/subscriptions/?hl=ja)
- [Google：Gemini 4 Argonの提供開始告知](https://blog.google/intl/en-in/products/introducing-gemini-4-argon/)
- [Antigravity：Argonのアプリ・CLI提供条件](https://antigravity.google/blog/gemini-4-argon-in-google-antigravity)
- [Geminiヘルプ：使用量上限（英語版）](https://support.google.com/gemini/answer/16275805?hl=en)
- [Geminiヘルプ：使用量上限（日本語版）](https://support.google.com/gemini/answer/16275805?hl=ja)
- [Google DeepMind：Argonの公開性能比較](https://deepmind.google/models/gemini/)
- [Google DeepMind：Argon評価方法](https://deepmind.google/models/evals-methodology/gemini-4-argon)
- [Artificial Analysis：Gemini 4 Argon high](https://artificialanalysis.ai/models/gemini-4-argon)
- [Google AI for Developers：ArgonのAPI仕様](https://ai.google.dev/gemini-api/docs/models/gemini-4-argon)
- [Google AI for Developers：API料金](https://ai.google.dev/gemini-api/docs/pricing)

## 次に考えたいこと
- [AIコーディングの契約と利用枠を確認する](https://nodus-lab.pages.dev/articles/ai-coding-subscriptions-real-rate-limits-token-economics.html)
- [サブスクとAPI、自分で運用するAIの費用を分ける](https://nodus-lab.pages.dev/articles/personal-ai-vps-home-server-subscription.html)
