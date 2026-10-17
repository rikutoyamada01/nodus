# MacでローカルLLMは動く？必要メモリとGPUとの選び方

> 手持ちのMacでOllamaを試す手順から、メモリ不足の確認、GPU搭載PCとの比較まで。買い足す前に必要な条件を整理します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/local-llm-hardware-mac-unified-memory-vs-rtx-gpu-tokens-per-watt
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/local-llm-hardware-mac-unified-memory-vs-rtx-gpu-tokens-per-watt.csv

## 訂正について
旧版の74環境集計、機種別tok/s、ワット効率、VRAMに収まる条件の断定は、採用した測定と集計手順を再現できないため撤回しました。必要なメモリと測定条件を確認する選び方へ改訂しました。

---

- **Category**: Cloud & AI Infrastructure
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-15

## 選び方の要点
- 対応するMacならOllamaでローカルLLMを試せる。まずOS、チップ、メモリを確認する。
- 必要メモリはモデルと文脈長で変わる。搭載容量だけで判断せず、実行中の使用量を見る。
- MacやGPUを買い足す前に、同じ日本語の課題で品質と待ち時間を比べる。


## 選択肢の比較表
| 候補 | 検討する理由 | 確認すること | 費用の範囲 |
| --- | --- | --- | --- |
| 手元のPCで試す | 初期支出を増やさず用途を確かめる | モデル、量子化、メモリ、待ち時間 | 追加電力と必要な保存領域 |
| Apple SiliconのMac | 統合メモリ構成や普段の作業も含めて選ぶ | 推論ソフトの対応、利用可能メモリ、性能 | 本体の構成、保存領域、他用途との共用 |
| GPU搭載PC・増設 | 対応ソフトや既存PCを活かしたい | VRAM、電源、冷却、実行バックエンド | GPUだけでなく電源やケースの増設 |
| API・クラウド併用 | 大きな処理を不定期に行う | 品質、送信データ、料金、利用条件 | 利用量に応じた料金と運用費 |

## 詳細解説・原因分析
### 手持ちのMacで動く？OSとチップを確認する
Macでも、対応する実行ソフトとモデルを選べばローカルLLMを試せます。この記事ではOllamaを例にします。2026年10月15日確認の公式要件はmacOS Sonoma 14以降で、Apple MシリーズはCPUとGPU、Intelのx86 MacはCPUのみの対応です。Appleメニューの「このMacについて」でチップまたはプロセッサ、macOSのバージョン、搭載メモリを確認し、モデルを保存するディスクの空き容量も用意します。これはOllamaの要件で、すべての推論ソフトに共通する条件ではありません。
参照: [Ollama：macOSの要件とインストール](https://docs.ollama.com/macos)
参照: [Apple：Appleシリコン搭載Macの確認方法](https://support.apple.com/en-us/116943)

### 1. Ollamaをインストールする
Ollama公式サイトからmacOS版をインストールし、アプリを起動します。
参照: [Ollama：macOSの要件とインストール](https://docs.ollama.com/macos)
参照: [Ollama：クイックスタート](https://docs.ollama.com/quickstart)

### 2. モデルを起動して質問する
ターミナルで ollama run gemma3:1b を実行します。初回はモデルをダウンロードするため、通信と保存領域が必要です。短い日本語の質問を入力し、回答が返ることを確認します。このモデルは導入確認の例で、日本語の品質を保証する推奨モデルではありません。
参照: [Ollama：CLIリファレンス](https://docs.ollama.com/cli)
参照: [Ollama：Gemma 3 1Bの配布ページ](https://ollama.com/library/gemma3:1b)
参照: [Ollama：クイックスタート](https://docs.ollama.com/quickstart)

### 3. 使用状況を確認して終了する
別のターミナルで ollama ps を実行し、PROCESSOR欄でCPU・GPUの使用状況を確認します。会話は /bye で終了します。モデルをメモリから外す場合は ollama stop gemma3:1b を実行します。
参照: [Ollama：CLIリファレンス](https://docs.ollama.com/cli)
参照: [Ollama：文脈長と必要メモリ](https://docs.ollama.com/context-length)
参照: [Ollama：FAQ](https://docs.ollama.com/faq)
参照: [Ollama：クイックスタート](https://docs.ollama.com/quickstart)

### 最初に決めるのは、モデルではなく仕事
日本語の相談、文書検索、コード補助など、毎週行いたい仕事を選びます。求める品質と待てる時間を決めて、手元のPCやAPIで試します。大きなモデルを動かせたという事実だけでは、その機器に購入額を払う価値があるかは分かりません。

### 必要メモリは何GB？重みの容量だけで決めない
8GB・16GBなどの搭載容量だけでは、使いたいモデルが快適に動くかは決まりません。モデルの保存ファイルのほかに、実行時のキャッシュや作業領域が必要です。文脈長、量子化、同時利用数、実行ソフトの設定でも使用量が変わり、macOSやほかのアプリにもメモリが必要です。Ollamaの公式資料も文脈長を大きくすると必要メモリが増えると説明しています。旧版のように特定のパラメータ数なら必ず一定容量に収まるとは断定せず、使うファイルと設定で実行中の使用量を確認します。
参照: [Ollama：文脈長と必要メモリ](https://docs.ollama.com/context-length)
参照: [Apple：アクティビティモニタでメモリ使用状況を表示](https://support.apple.com/guide/activity-monitor/view-memory-usage-actmntr1004/mac)
参照: [Ollama：FAQ](https://docs.ollama.com/faq)

### メモリ不足や遅さを感じたら、条件を一つずつ変える
アクティビティモニタの「メモリ」でメモリプレッシャーとスワップ使用領域を見て、実行前後を比較します。Ollamaでは ollama ps で実際の文脈長とCPU・GPUの使用状況も確認します。負荷が大きい場合は、不要なアプリやほかのモデルを終了し、短い会話と小さいモデルで再確認します。文脈長を大きく設定していたならOllamaの設定で下げ、必要な文書が収まる範囲を探します。文脈を減らすと扱える情報も減るため、回答の品質も確かめます。スワップの値だけで原因を断定せず、変えた条件と待ち時間を一緒に記録します。
参照: [Ollama：CLIリファレンス](https://docs.ollama.com/cli)
参照: [Ollama：文脈長と必要メモリ](https://docs.ollama.com/context-length)
参照: [Apple：アクティビティモニタでメモリ使用状況を表示](https://support.apple.com/guide/activity-monitor/view-memory-usage-actmntr1004/mac)

### 入力処理と生成を別に比べる
llama-benchの公式READMEでは、プロンプト処理のppと生成のtgを分けた測定例が示されています。長い文書を読み込む用途と短い会話を続ける用途では、注目する項目が違います。同じモデルファイル、ソフトの版、バックエンド、文脈条件を記録して比較し、異なる条件のログから機種の順位を作らないようにします。
参照: [llama.cpp：llama-bench README](https://github.com/ggml-org/llama.cpp/blob/master/tools/llama-bench/README.md)

### 公開ログは、同じ条件かを確かめる
llama.cppのApple Silicon向けディスカッションには利用者の報告があります。ただし投稿の機器、モデル、ソフトの版、設定は一定ではありません。個別の構成の参考として読めても、そのまま最近のすべてのMacやGPUの性能に一般化することはできません。この記事では、これらの投稿から比較用の中央値を再計算していません。
参照: [llama.cpp：Apple Siliconの性能報告](https://github.com/ggml-org/llama.cpp/discussions/4167)

### 本体価格と、使い続ける費用
GPUの増設では、必要な電源、ケース、冷却、騒音も含めます。電力効率を比較するならGPU単体の表示値と、PC全体のコンセントでの消費を混ぜず、同じ仕事の完了までに使った電力量を見る方法があります。不定期にしか使わないならAPIやクラウドも候補にし、手元で動かす目的と費用を照らし合わせます。

## 記事の範囲
公式資料で確認できる機能・仕様と、編集上の比較手順を整理しています。購入価格や性能の順位を確定する実機比較は行っていません。計算例を示す場合は仮定を明記しています。


## 参考資料
- [llama.cpp：llama-bench README](https://github.com/ggml-org/llama.cpp/blob/master/tools/llama-bench/README.md)
- [llama.cpp：Apple Siliconの性能報告](https://github.com/ggml-org/llama.cpp/discussions/4167)
- [Ollama：macOSの要件とインストール](https://docs.ollama.com/macos)
- [Ollama：CLIリファレンス](https://docs.ollama.com/cli)
- [Ollama：Gemma 3 1Bの配布ページ](https://ollama.com/library/gemma3:1b)
- [Ollama：文脈長と必要メモリ](https://docs.ollama.com/context-length)
- [Apple：アクティビティモニタでメモリ使用状況を表示](https://support.apple.com/guide/activity-monitor/view-memory-usage-actmntr1004/mac)
- [Apple：Appleシリコン搭載Macの確認方法](https://support.apple.com/en-us/116943)
- [Ollama：FAQ](https://docs.ollama.com/faq)
- [Ollama：クイックスタート](https://docs.ollama.com/quickstart)

## 次に考えたいこと
- [パーソナルAIは、どこに置く？](https://nodus-lab.pages.dev/articles/personal-ai-vps-home-server-subscription)
- [自宅サーバー用ミニPC、CPU名だけで選んでいい？](https://nodus-lab.pages.dev/articles/mini-pc-ryzen-ai-hx370-8845hs-sustained-tdp-fan-noise-tests)
