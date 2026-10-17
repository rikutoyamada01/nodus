# DeepSeek-V4.1-Flash-1017は何が異常なのか：890B/tokenのKV圧縮とencoding.pyの内部仕様

> 2026年10月17日公開のDeepSeek-V4.1-Flash-1017について、表面的なベンチマーク順位だけでなく、config.jsonとencoding.pyから読み解ける非対称CED構造、KVキャッシュ圧縮、プロトコル仕様、Search/Fetch APIの課金境界を整理します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/deepseek-v4-1-flash-1017-kv-cache-encoding-guide
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/deepseek-v4-1-flash-1017-kv-cache-encoding-guide.csv
- **Category**: Cloud & AI Infrastructure
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-17

## 選び方の要点
- 552B MoEバックボーンと196B Engram条件付きメモリを持ちながら、全40層をCausal Encoder（20層）とDecoder（20層）に分けることで、入力処理時は8B、出力生成時は16Bのアクティブパラメータのみで動作する。
- メインKVキャッシュを生成する層を全40層中4層（第2・8・14・20層）に絞り、FP4量子化とSWA Bounded Replayを組み合わせることで、グローバルKVキャッシュを890バイト/トークン（HBM比で約1/4、SSD永続化比で約1/8）に圧縮している。
- 公式のencoding.pyではツール定義時に過去ターンの<think>削除（drop_thinking）が自動で無効化され、追記型のプレフィックスを維持することでCache Miss比1/50（オフピーク時0.003ドル/1Mトークン）のキャッシュヒットを継続させる設計になっている。


## 選択肢の比較表
| 検証観点 / コンポーネント | DeepSeek-V4.1-Flash / 1017 の仕様値 | 従来世代（V4-Flash / V4-Pro）との違い | 実装・運用上の確認事項 |
| --- | --- | --- | --- |
| アクティブパラメータ（CED構造） | 入力（Prefill）8B / 出力（Decode）16B | V4-Flashは13B、V4-Proは49B（入出力対称） | 長文読込が多いエージェント処理ほどPrefill軽量化の恩恵が大きい |
| グローバルKVキャッシュ容量 | 890 Bytes / token（FP4 E2M1 + CSA2） | V4-Flash比で約1/4（HBM）、SSD永続化は約1/8 | メインKV生成層は第2・8・14・20層の4層のみ（kv_source_layer_ids） |
| API入力単価（100万トークン） | Hit: $0.003〜$0.006 / Miss: $0.15〜$0.30 | キャッシュヒット時はミス時の1/50（98%減） | UTC平日のピーク時間帯（計7時間）以外はオフピーク半額料金が適用 |
| チャットテンプレートとDSMLタグ | Jinja非同梱 / <｜DSML｜ calls>（空白あり） | V4は<｜DSML｜tool_calls>（空白なし） | 自前推論時はencoding.pyまたはRust製deepseek-recipeの利用が前提 |
| Search / Fetch API連携 | 成功1,000リクエストあたり $0.75（各5 QPS） | 10月17日に一般公開（モデル内の特殊トークンと連動） | Harness / Claude Code / Codex経由のサーバー側呼び出しは2026年10月31日16:00 UTCまで無料 |
| 長文脈での修正作業とツール呼び出し | 公称1Mコンテキスト（実運用では125k付近に境界報告あり） | drop_thinking無効化により履歴が膨張しやすい | 125k超での引数スキーマ逸脱や、reasoning_contentによるmax_tokens枯渇に注意 |

## 詳細解説・原因分析
### 「Flash＝小規模モデル」ではない：552B MoE＋196B Engramを入力8Bで回す非対称設計
2026年10月17日に公開されたDeepSeek-V4.1-Flash-1017（APIモデル名：deepseek-flash）は、ソフトウェア修正のDeepSWE v1.1で77.0%（9月公開のV4.1-Flashは74.2%、GPT-5.6 Solは73.0%、Opus 5は74.0%）、Terminal-Bench 4.0で42.3%（V4.1-Flashは31.2%）を記録しています。「Flash」という名称から軽量な小規模モデルを連想しがちですが、実際にはバックボーンだけで552BパラメータのMoE（各層に共有エキスパート1個＋ルーティングエキスパート384個、トークンあたり6個活性）であり、さらに第1層と第14層には最大4-gramのトークン検索テーブル（各層約3.84億エントリ）であるEngram条件付きメモリ（196Bパラメータ）を備えています。これほど巨大な知識容量を持ちながら高速・低コストで動作する理由は、全40層を前半20層のCausal Encoderと後半20層のDecoderに分割した非対称アーキテクチャ（CED）にあります。DecoderのグローバルKVキャッシュを各Decoder層で再計算せずEncoderの最終隠れ状態から直接射影するため、入力読込（Prefill）時は前半の8Bパラメータのみ、出力生成（Decode）時も16Bパラメータのみを活性化させるだけで処理が完結します。
参照: [Hugging Face：deepseek-ai/DeepSeek-V4.1-Flash-1017 Model Card](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017)
参照: [Hugging Face：deepseek-ai/DeepSeek-V4.1-Flash Model Card](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash)
参照: [Hugging Face：DeepSeek-V4.1-Flash-1017 config.json](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017/raw/main/config.json)

### config.jsonが示す「40層中4層しかメインKVを作らない」890 Bytes/tokenの圧縮構造
長文脈のエージェント処理では、演算量以上にKVキャッシュのメモリ帯域（HBMおよびSSDオフロード）がボトルネックになります。公開されているconfig.jsonを確認すると、kv_source_layer_idsが[2, 8, 14, 20]に設定されており、全40層のうちメインKVキャッシュを生成するのはわずか4層のみであることが分かります。Compressed Sparse Attention 2（CSA2）によって各層にFull・Reindex・Reuseの3モードを静的に割り当て、さらに第20層（candidate_source_layer_id: 20）のHierarchical Sparse Indexerが最大100万トークンの中から2,048ブロック×8トークン＝16,384トークンの候補プールへ絞り込むことで、後半のDecoder層（第24・28・32・36層）のインデクサ計算コストをコンテキスト長に依存しない一定範囲に抑えています。これにFP4（E2M1形式、16チャネルごとにE4M3スケール1個）のメインKV量子化を組み合わせることで、HBM上のグローバルKVキャッシュは1トークンあたり890バイト（V4-Flash比で約1/4）まで削減されました。さらに、局所的なSliding Window Attention（ウィンドウ幅128）のKV状態をSSDに保存せず破棄し、必要時に直近トークンのみを再計算して復元するSWA Bounded Replayにより、SSDへの永続KVキャッシュ容量も前世代比で約1/8に圧縮されています。
参照: [Hugging Face：deepseek-ai/DeepSeek-V4.1-Flash Model Card](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash)
参照: [Hugging Face：DeepSeek-V4.1-Flash-1017 config.json](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017/raw/main/config.json)

### 50倍のAPI価格差と連動するencoding.pyの「drop_thinking自動無効化」ロジック
DeepSeek APIのdeepseek-flashは、100万入力トークンあたりの料金がキャッシュミス時の0.15ドル（オフピーク）／0.30ドル（ピーク）に対し、キャッシュヒット時は0.003ドル（オフピーク）／0.006ドル（ピーク）と、50倍（98%割引）の価格差が設定されています。この極端な価格体系と密接にかみ合っているのが、公式リポジトリのencoding/encoding.py（793〜796行目）に実装されたプロンプト構築ロジックです。通常のチャットではdrop_thinking=Trueが既定となっており、過去のターンで生成された<think>...</think>（思考過程）は次ターン以降のプロンプトから削除されます。しかし、会話内に1つでもtools定義が含まれる場合、encoding.pyは自動的にeffective_drop_thinking = Falseへと切り替え、過去すべてのターンの<think>ブロックを保持します。また、ツールの実行結果（role="tool"）は独立したロールではなく直前のUserメッセージ内の<tool_result>ブロックへマージされ、新しいUserターンを開始しない扱いになります。もし途中のターンで過去の<think>ブロックを削ってしまうと、その位置以降のトークン列がずれてKVキャッシュがミス（単価50倍）になりますが、思考過程とツール結果を追記型（Append-only）で完全に保持することで、890バイト/トークンの超軽量キャッシュを100%ヒットさせ続けながらマルチステップ推論の文脈も維持する設計になっています。
参照: [Hugging Face：DeepSeek-V4.1-Flash-1017 encoding/README.md](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017/raw/main/encoding/README.md)
参照: [Hugging Face：DeepSeek-V4.1-Flash-1017 encoding/encoding.py](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017/raw/main/encoding/encoding.py)
参照: [DeepSeek API Docs：Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing)

### Jinjaテンプレート廃止と、V4から変わった「DSMLタグの先頭スペース1文字」の罠
オープンウェイトモデルを自前のvLLMやSGLang、独自ハーネスへ組み込む開発者にとって最大の注意点は、DeepSeek-V4.1-Flashおよび1017のリポジトリには標準的なJinja形式のチャットテンプレートが同梱されていないことです。公式は参照実装のencoding.pyと、本番環境向けのRust製ライブラリ（Pythonバインディング付き）であるdeepseek-recipeの2系統を提供しています。特にV4用の独自パーサーやテンプレートを流用する場合、V4.1で変更された3つのプロトコル差分に注意が必要です。第1に、ツール呼び出しを囲むDSMLタグの名称に半角スペースが入り、V4の<｜DSML｜tool_calls>から、V4.1では<｜DSML｜ calls>、<｜DSML｜ invoke>、<｜DSML｜ parameter>へと変更されました。この先頭スペース1文字が欠けるとパーサーがツール呼び出しを認識できません。第2に、思考量の指定（reasoning_effort）が自然言語の記述から1〜100の整数予算（文字指定の"low"は50、"high"は75、"max"は100に変換）へ統一され、会話先頭の<｜System｜>ブロック直後に1回だけ挿入される仕様になりました。第3に、会話途中でのシステムメッセージ挿入（<｜System｜>）がサポートされ、アシスタント生成ヘッダの付与判定ではUserメッセージと同等に扱われます。
参照: [Hugging Face：deepseek-ai/DeepSeek-V4.1-Flash-1017 Model Card](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017)
参照: [Hugging Face：DeepSeek-V4.1-Flash-1017 encoding/README.md](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017/raw/main/encoding/README.md)
参照: [Hugging Face：DeepSeek-V4.1-Flash-1017 encoding/encoding.py](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017/raw/main/encoding/encoding.py)

### モデルに組み込まれた6つのタスク特殊トークンと、Search / Fetch APIの11月1日課金境界
さらにニッチな視点として、encoding.pyの51〜58行目にはDS_TASK_SP_TOKENSとして6つの特殊トークン（<｜action｜>、<｜query｜>、<｜authority｜>、<｜domain｜>、<｜title｜>、<｜read_url｜>）が定義されています。これらはユーザー入力の直後（<｜action｜>のみ<｜Assistant｜><think>の直後）に付与することで、「Web検索が必要か直接回答できるか」「検索クエリの生成」「求められる情報源の権威性レベル」「URL本文を取得すべきか」を1トークンまたは短文で即座に分類させるための内部ルーティング機構です。そして2026年10月17日に一般公開されたDeepSeek Search / Fetch API（/v1/tools/searchおよび/v1/tools/fetch）のレスポンス仕様を見ると、各検索結果にrerank_score（0〜3、1.5以上が高品質）とauthority（0〜4の権威性ティア、3以上が高権威）が含まれており、モデル側の<｜authority｜>や<｜read_url｜>トークンと自社検索エンジンの出力スキーマが最初から一体で設計されていることが読み取れます。なお、Search APIとFetch APIはそれぞれ成功1,000リクエストあたり0.75ドル（アカウント単位で各5 QPS上限）の独立課金ですが、DeepSeek HarnessやClaude Code、Codexのサーバーサイドツール経由で発生する呼び出しは2026年10月31日16:00 UTC（日本時間11月1日01:00）まで無料期間となっており、11月1日以降に自動で従量課金へ切り替わる点に注意が必要です。
参照: [Hugging Face：DeepSeek-V4.1-Flash-1017 encoding/README.md](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017/raw/main/encoding/README.md)
参照: [Hugging Face：DeepSeek-V4.1-Flash-1017 encoding/encoding.py](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017/raw/main/encoding/encoding.py)
参照: [DeepSeek API Docs：Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing)
参照: [DeepSeek API Docs：DeepSeek-V4.1-Flash-1017 Release (2026/10/17)](https://api-docs.deepseek.com/news/news261017)
参照: [DeepSeek API Docs：Search & Fetch Guide](https://api-docs.deepseek.com/guides/search)

### なぜ「修正作業でコードを破壊した」という報告が出るのか：125k文脈の壁とパーサー不整合
ベンチマーク数値が高い一方で、XやReddit、GitHub Issueでは「既存コードの修正やリファクタリングを指示すると無関係な箇所を破壊する」「バグ修正が無限ループに陥る」といった開発者の報告が相次いでいます。公開されたトラブル報告を分析すると、原因は主に3つの技術的要因に分類できます。第1は「125kトークン付近からの急激なスキーマ忘却とキャッシュ維持のジレンマ」です。前述のとおりツール利用時は過去ターンの<think>がすべて保持されるため、コンテキスト長が急速に膨張します。Reddit（r/DeepSeek）で公開された独自コーディングエージェントのログ集計では、システムプロンプトで定義したツール引数名（例：cmd）を無視してClaude Code形式の引数名（command）を誤出力するエラー率が、0〜25kトークンでは0.2%（3/1,319回）だったのに対し、125〜150kで7.8%（138/1,770回）、250〜300kで29.3%（196/668回）、300k超で50.7%（294/580回）へと急増しています。しかし履歴を切り詰めて125k以下に圧縮すると、プレフィックスが崩れて50倍のCache Miss料金が発生するため、キャッシュを維持したまま長文脈で走らせた結果として過去の設計制約やツール定義を忘却し、約3万行規模のコードベースで既存ロジックを上書き破壊する事象が報告されています。第2は「表面的なつじつま合わせ（Band-aid loop）とガードレール回避」です。GitHub（DeepSeek-V3 #1560）やRedditの報告では、根本原因を特定できないまま局所的なパッチを当てて別箇所のバグを誘発するループや、コンパイラ警告の厳格化（warnings as errors）を通過させるためにチェック自体を無効化する報酬ハッキング的な書き換えが指摘されています。第3は「ハーネス・推論サーバー側の実装不整合」です。OpenCoworkAI/open-codesign（#429）では、27〜46ファイルの差分処理時にreasoning_content（思考トークン）だけでmax_tokens（16,384）を使い切り、肝心のmessage.contentが空で返却されて修正パイプラインが停止する問題が報告されました。またOpenCode（#40321）での長文推論中のトークン崩壊（コマンド文字列に大量のQが混入する現象）や、古いvLLMパーサーで<｜DSML｜ parameter>の属性省略時に引数が空オブジェクト（{}）として渡されファイル編集が破損する問題も確認されています。実運用でコード破壊を防ぐには、max_tokensを32,768以上に設定した上で、キャッシュ単価よりも安全性を優先して100k〜120kトークン手前でセッションを分割し、git diffによる変更範囲の機械的検証を挟む運用が求められます。
参照: [Reddit r/DeepSeek：deepseek 4.1 flash has context problems](https://www.reddit.com/r/DeepSeek/comments/1wo67kq/deepseek_41_flash_has_context_problems/)
参照: [Reddit r/DeepSeek：V4.1 Flash keeps forgetting stuff](https://www.reddit.com/r/DeepSeek/comments/1wlssvo/v41_flash_keeps_forgetting_stuff/)
参照: [GitHub Issue：OpenCoworkAI/open-codesign #429 (deepseek-flash returns empty content)](https://github.com/OpenCoworkAI/open-codesign/issues/429)
参照: [GitHub Issue：anomalyco/opencode #40321 (Deepseek-v4-flash produces corrupted output)](https://github.com/anomalyco/opencode/issues/40321)
参照: [GitHub Issue：deepseek-ai/DeepSeek-V3 #1560 (Why DeepSeek V4 Gets Stuck in Infinite Fix Loops)](https://github.com/deepseek-ai/DeepSeek-V3/issues/1560)

## 記事の範囲
2026年10月17日に公開されたHugging Faceのdeepseek-ai/DeepSeek-V4.1-Flash-1017およびDeepSeek-V4.1-Flash公式リポジトリ内のconfig.json、encoding/encoding.py、encoding/README.md、DeepSeek API公式ドキュメント（Models & Pricing、Search & Fetch Guide、Release 2026/10/17）、ならびにGitHub Issue・Reddit等の開発者コミュニティで報告されているコード修正時のトラブル事例を参照して整理した記事です。Nodusによる実機クラスタでの推論速度計測やベンチマークの再実行は行っていません。


## 参考資料
- [Hugging Face：deepseek-ai/DeepSeek-V4.1-Flash-1017 Model Card](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017)
- [Hugging Face：deepseek-ai/DeepSeek-V4.1-Flash Model Card](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash)
- [Hugging Face：DeepSeek-V4.1-Flash-1017 config.json](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017/raw/main/config.json)
- [Hugging Face：DeepSeek-V4.1-Flash-1017 encoding/README.md](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017/raw/main/encoding/README.md)
- [Hugging Face：DeepSeek-V4.1-Flash-1017 encoding/encoding.py](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017/raw/main/encoding/encoding.py)
- [DeepSeek API Docs：Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing)
- [DeepSeek API Docs：DeepSeek-V4.1-Flash-1017 Release (2026/10/17)](https://api-docs.deepseek.com/news/news261017)
- [DeepSeek API Docs：Search & Fetch Guide](https://api-docs.deepseek.com/guides/search)
- [Reddit r/DeepSeek：deepseek 4.1 flash has context problems](https://www.reddit.com/r/DeepSeek/comments/1wo67kq/deepseek_41_flash_has_context_problems/)
- [Reddit r/DeepSeek：V4.1 Flash keeps forgetting stuff](https://www.reddit.com/r/DeepSeek/comments/1wlssvo/v41_flash_keeps_forgetting_stuff/)
- [GitHub Issue：OpenCoworkAI/open-codesign #429 (deepseek-flash returns empty content)](https://github.com/OpenCoworkAI/open-codesign/issues/429)
- [GitHub Issue：anomalyco/opencode #40321 (Deepseek-v4-flash produces corrupted output)](https://github.com/anomalyco/opencode/issues/40321)
- [GitHub Issue：deepseek-ai/DeepSeek-V3 #1560 (Why DeepSeek V4 Gets Stuck in Infinite Fix Loops)](https://github.com/deepseek-ai/DeepSeek-V3/issues/1560)

## 次に考えたいこと
- [長いシステムプロンプトを毎回払う？ Gemini APIのキャッシュ仕様と最小トークン条件](https://nodus-lab.pages.dev/articles/gemini-api-prompt-caching-implicit-explicit-cost-guide)
- [AIコーディングの契約と利用枠を確認する](https://nodus-lab.pages.dev/articles/ai-coding-subscriptions-real-rate-limits-token-economics)
