# Ollamaのコンテキスト長（num_ctx）のデフォルト確認と変更・設定方法：VRAM別の目安

> 128kや256k対応のローカルLLMをダウンロードしたのに長い文章を途中で忘れるとき、実際に割り当てられているコンテキスト長の確認方法と設定手順を公式資料から整理します。

- **Canonical URL**: https://nodus-lab.pages.dev/articles/ollama-context-length-vram-default-memory-guide
- **CSV Comparison Table**: https://nodus-lab.pages.dev/datasets/ollama-context-length-vram-default-memory-guide.csv
- **Category**: Cloud & AI Infrastructure
- **Article type**: 選び方・公式資料から整理（実測なし）
- **Data Updated**: 2026-10-16

## 選び方の要点
- モデル自体が128kトークンに対応していても、Ollamaの既定では24GiB未満のVRAM環境で4k（4,096トークン）に制限される。
- 公式資料では24〜48GiB VRAMで32k、48GiB以上で256kが既定値と案内されており、Web検索やコーディングエージェント用途では64,000トークン以上の設定が推奨されている。
- 文脈長を増やすと必要メモリが増えCPUオフロードによる速度低下が起きやすいため、変更後は必ず ollama ps で CONTEXT と PROCESSOR（GPU比率）を確認する。


## 選択肢の比較表
| 利用環境・設定箇所 | 公式資料に記載された既定値・方法 | 変更時の指定方法 | 変更後に確認すること |
| --- | --- | --- | --- |
| VRAM 24GiB未満の環境 | 4k（4,096トークン） | アプリ設定スライダーまたは OLLAMA_CONTEXT_LENGTH | ollama ps でCPUへ溢れていないか確認 |
| VRAM 24〜48GiBの環境 | 32kトークン（FAQでは一律4,096表記あり） | 用途に応じて 64000 等を明示指定 | 実際に割り当てられた CONTEXT 列の数値 |
| VRAM 48GiB以上の環境 | 256kトークン | モデルの最大長を超えない範囲で調整 | 複数モデル同時起動時のメモリ圧迫 |
| CLI対話 / API呼び出し単位 | サーバー側の既定値に従う | /set parameter num_ctx または API options.num_ctx | リクエスト単位でメモリ使用量が変わる点 |

## 詳細解説・原因分析
### モデルの最大仕様が128kでも初期設定のままでは4kで切られることがある
配布ページに「128k context」と書かれたモデルをダウンロードしても、そのまま実行しただけで128kトークンすべてが使われるとは限りません。2026年10月16日確認のOllama公式ドキュメント（Context length）では、利用可能なVRAM容量に応じて既定のコンテキスト長が「24GiB未満：4k」「24〜48GiB：32k」「48GiB以上：256k」に設定されると記載されています。また、同サイトのFAQページでは「既定で4096トークンを使用する」とも説明されており、一般的な8GB〜16GB VRAMのGPUやメモリ環境では、明示的に変更しない限り約4,000トークン（日本語で数千文字程度）を超える文脈は保持されません。
参照: [Ollama Docs：Context length（VRAM別既定値と設定方法）](https://docs.ollama.com/context-length)
参照: [Ollama Docs：FAQ（num_ctxとOLLAMA_CONTEXT_LENGTH）](https://docs.ollama.com/faq)

### エージェントや検索連携で使うなら64,000トークン以上への変更が目安になる
公式ドキュメントでは、Web検索、AIエージェント、コーディングツールのように長い入出力を伴うタスクでは、コンテキスト長を少なくとも64,000トークン以上に設定することが推奨されています。設定を変更する方法は3通りあります。デスクトップアプリを使っている場合は設定画面（Settings）のスライダーから変更でき、サーバー起動時に一括指定する場合は環境変数 `OLLAMA_CONTEXT_LENGTH=64000 ollama serve` を使います。また、APIリクエストごとに変えたい場合は、リクエストJSONの `options` 内に `"num_ctx": 64000` のように指定します。
参照: [Ollama Docs：Context length（VRAM別既定値と設定方法）](https://docs.ollama.com/context-length)
参照: [Ollama Docs：FAQ（num_ctxとOLLAMA_CONTEXT_LENGTH）](https://docs.ollama.com/faq)

### 変更後は必ず ollama ps で実効コンテキスト長とGPU割当比率を確認する
コンテキスト長を増やすと、モデルの重みとは別にKVキャッシュ用のメモリ消費が大きく増加します。VRAMや統合メモリに収まりきらなくなると、処理の一部がCPU側へオフロードされ、応答速度が大幅に低下します。公式ドキュメントでも、設定変更後はターミナルで `ollama ps` を実行し、`CONTEXT` 列が意図した数値になっているか、そして `PROCESSOR` 列が `100% GPU` になっているか（CPUへ溢れていないか）を確認する手順が示されています。
参照: [Ollama Docs：Context length（VRAM別既定値と設定方法）](https://docs.ollama.com/context-length)
参照: [Ollama Docs：CLI Reference](https://docs.ollama.com/cli)

### メモリを増設する前に用途ごとの必要長さを分けて運用する
すべての作業で常に64kや128kのコンテキストを開きっぱなしにすると、手元のメモリをすぐに使い切ってしまいます。短い質疑応答や翻訳では既定の4k〜8kのまま高速に動かし、長いソースコードや資料を渡すときだけAPIの `num_ctx` や `/set parameter num_ctx` で一時的に広げる運用にすれば、高価な大容量GPUやMacへ買い替えなくても手持ち環境でこなせる範囲が広がります。
参照: [Ollama Docs：Context length（VRAM別既定値と設定方法）](https://docs.ollama.com/context-length)
参照: [Ollama Docs：FAQ（num_ctxとOLLAMA_CONTEXT_LENGTH）](https://docs.ollama.com/faq)

## よくある疑問と回答 (FAQ)
### Q. Ollamaのコンテキスト長（Context length）のデフォルトは何トークンですか？
A. モデル自体が128kトークンに対応していても、Ollamaの既定ではVRAM 24GiB未満の環境で4k（4,096トークン）に設定されます。VRAM 24〜48GiBでは32k、48GiB以上では256kが既定値となります。

### Q. Ollamaのコンテキスト長を変更・設定し、現在有効な値を確認する方法は？
A. 環境変数 `OLLAMA_CONTEXT_LENGTH=64000` の指定、APIリクエストやModelfileでの `PARAMETER num_ctx 64000` 指定で変更できます。変更後は `ollama ps` コマンドを実行すると、現在ロードされているモデルの `CONTEXT` 列とGPU/CPU割当比率（`PROCESSOR`）を確認できます。

## 記事の範囲
2026年10月16日にOllama公式ドキュメント（Context length、FAQ、CLI Reference）を確認して整理した記事です。コンテキスト長ページ（VRAM別4k/32k/256k）とFAQページ（4096トークン）の記載差も含めて照合しています。各モデルでの実測メモリ消費量や生成速度は測定していません。


## 参考資料
- [Ollama Docs：Context length（VRAM別既定値と設定方法）](https://docs.ollama.com/context-length)
- [Ollama Docs：FAQ（num_ctxとOLLAMA_CONTEXT_LENGTH）](https://docs.ollama.com/faq)
- [Ollama Docs：CLI Reference](https://docs.ollama.com/cli)

## 次に考えたいこと
- [MacでローカルLLMは動く？ 必要メモリ・スペックとOllama構築、GPUとの比較](https://nodus-lab.pages.dev/articles/local-llm-hardware-mac-unified-memory-vs-rtx-gpu-tokens-per-watt)
- [AIエージェントの24時間常駐：ラズパイ・VPS・ミニPCのどれを選ぶ？](https://nodus-lab.pages.dev/articles/always-on-personal-ai-raspberry-pi-vps-mini-pc)
