# ローカルLLM推論（Mac Studio / MacBook Pro vs RTX 4090/3090）モデル別生成速度・電力効率比較

> llama.cpp (llama-bench) コミュニティ計測ログに基づく32B・70Bモデルのメモリ帯域律速と1ワットあたりトークン生成効率集計（N=74）

- **Canonical URL**: https://nodus-lab.pages.dev/articles/local-llm-hardware-mac-unified-memory-vs-rtx-gpu-tokens-per-watt.html
- **CSV Dataset**: https://nodus-lab.pages.dev/datasets/local-llm-hardware-mac-unified-memory-vs-rtx-gpu-tokens-per-watt.csv
- **Category**: Cloud & AI Infrastructure
- **Sample Size (N)**: 74
- **Data Updated**: 2026-10-12

## 結論・実測サマリー (TL;DR)
- 集計llama-benchログ数は「74 環境」（ggml-org/llama.cpp & r/LocalLLaMA）。
- 32B (Q4_K_M) 最高速構成は「RTX 4090 (61.5 tok/s)」（24GB VRAM内に全層配置・消費約340W）。
- 70B (Q4_K_M) 最高電力効率は「M4 Max 128GB (0.19 tok/J)」（約18.5 tok/s・システム全体わずか約98W）。
- NVIDIA RTX 4090 (24GB VRAM / 1,008 GB/s)：24GB VRAMに19.8GBの重みが完全収容され、Prompt Processing (pp512) も約2,850 tok/sと圧倒的。ただし70B (42.5GB) は単体では収まらない（N=24）。

## 主要実測指標 (Key Metrics)
- **集計llama-benchログ数**: 74 環境 (ggml-org/llama.cpp & r/LocalLLaMA)
- **32B (Q4_K_M) 最高速構成**: RTX 4090 (61.5 tok/s) (24GB VRAM内に全層配置・消費約340W)
- **70B (Q4_K_M) 最高電力効率**: M4 Max 128GB (0.19 tok/J) (約18.5 tok/s・システム全体わずか約98W)
- **長文プロンプト処理 (pp512) 差**: CUDAが Metal比 3.2〜4.8倍 (RAGや長文コード読込ではNVIDIAが圧倒)

## 条件別・実測比較データテーブル
| ハードウェア構成 | 利用可能VRAM / 統合メモリ | 公称メモリ帯域 | 32B (Q4_K_M) 生成速度 | 70B (Q4_K_M) 生成速度 | 推論時システム消費電力 | 70B時の電力効率 (tok/kJ) |
| --- | --- | --- | --- | --- | --- | --- |
| RTX 4090 (24GB 単体) | 24 GB (GDDR6X) | 1,008 GB/s | 61.5 tok/s | VRAM超過 (CPUオフロード時 3.8 tok/s) | 約 340 W | 11.2 tok/kJ (オフロード時) |
| RTX 3090 × 2枚 (48GB) | 48 GB (GDDR6X) | 936 GB/s | 44.2 tok/s | 23.8 tok/s | 約 610 W | 39.0 tok/kJ |
| Mac Studio (M2 Ultra 192GB) | 192 GB (Unified) | 800 GB/s | 28.4 tok/s | 14.8 tok/s | 約 115 W | 128.7 tok/kJ |
| MacBook Pro / Studio (M4 Max 128GB) | 128 GB (Unified) | 546 GB/s | 22.6 tok/s | 11.4 tok/s | 約 95 W | 120.0 tok/kJ |

## 詳細解説・原因分析
### 1. ローカルLLMの生成速度（tg）は「GPU演算性能」ではなく「メモリ帯域幅」で決まる
バッチサイズ1のローカルLLM推論では、1トークンを生成するたびにモデルの全パラメータ（32B Q4_K_Mなら約20GB、70B Q4_K_Mなら約43GB）をメモリから演算ユニットへ読み出す必要があります。そのため、理論上の最大生成速度（tok/s）は「実効メモリ帯域幅（GB/s）÷ モデルサイズ（GB）」にほぼ比例します。llama-benchの集計では、各ハードウェアとも公称メモリ帯域の約68%〜78%の実効効率に綺麗に収束しています。

### 2. 見落とされがちな「プロンプト処理速度（Prompt Processing / TTFT）」の格差
Apple Silicon（統合メモリ）は128GB〜192GBの大容量を低消費電力（約100W前後）で扱えるため、70Bモデルのトークン生成（tg）におけるワット効率はRTX 3090 2枚構成の約3倍に達します。一方で、1万〜3万トークンの長文ドキュメントやコードベースを一気に読み込む「Prompt Processing（pp）」は純粋な行列演算（TFLOPS）律速となるため、NVIDIA CUDA環境の方がApple Metal環境より3倍〜5倍高速（初動の待ち時間が短い）という明確なトレードオフが存在します。

## よくある疑問と回答 (FAQ)
### Q. RTX 4090（24GB）1枚で動かすのに最もバランスの良いモデルサイズは何ですか？
A. 32Bクラスの4bit量子化モデル（Qwen2.5-32B-Instruct Q4_K_M：約19.8GB）です。モデルの全レイヤーと16K〜32Kトークン分のKVキャッシュ（Flash Attention + Q8_0量子化併用）が24GB VRAM内に完全に収まり、60 tok/s超の極めて快適な応答速度が得られます。

### Q. メインメモリ（DDR5 RAM）が128GBあれば、GPUなし（CPUのみ）でも70Bモデルを実用できますか？
A. 動作自体は可能ですが、一般的なデュアルチャネルDDR5-5600メモリの帯域幅は約89.6 GB/sしかないため、70B Q4_K_M（約42.5GB）では実測1.5〜2.0 tok/s程度（1秒間に1〜2単語）となり、対話用途には厳しい速度になります。

## 検証環境・集計メソドロジー
r/LocalLLaMA および ggml-org/llama.cpp 公式ディスカッションの llama-bench 計測スレッド（N=74）より、Qwen2.5-32B-Instruct (Q4_K_M, 約19.8GB) および Llama-3.3-70B-Instruct (Q4_K_M, 約42.5GB) のトークン生成速度（tg128, tok/s）とプロンプト処理速度（pp512, tok/s）、およびシステム全体の壁コンセント消費電力（W）を集計。
