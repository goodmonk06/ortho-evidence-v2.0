# 歯科矯正エビデンス生成システム

歯科矯正治療のエビデンスベースの推奨事項を提供するウェブアプリケーションです。患者の年齢と歯列問題に基づいて、科学的根拠に基づく矯正必要性の評価、タイミング推奨、リスク評価を生成します。

## 機能概要

- **矯正必要性スコア**: 患者の年齢と歯列問題に基づいた総合的な矯正必要性の評価
- **年齢別リスク分析**: 年齢に応じた将来的な歯科リスクの評価
- **問題別効果データ**: 各種歯列問題に対する矯正治療の効果とエビデンス
- **経済的影響評価**: 矯正治療の長期的な経済メリットの計算
- **将来シナリオ比較**: 矯正治療を受けた場合と受けなかった場合の将来予測
- **PubMed論文連携**: 最新の歯科矯正研究論文の自動収集と分析
- **エビデンスレベル評価**: 推奨事項の科学的根拠の強さの表示
- **レポート生成**: 詳細なHTML/PDFレポートの作成

## システム構成

このシステムは以下のコンポーネントで構成されています：

- **データベース**: SQLiteデータベースによる研究論文とエビデンスデータの管理
- **エビデンス処理モジュール**: 論文データからエビデンスを抽出・分析するPythonモジュール
- **Webアプリケーション**: Streamlitによるインタラクティブなユーザーインターフェース
- **PubMed API連携**: 最新の研究論文を自動収集するためのAPI連携

## 技術スタック

- **言語**: Python 3.7以上
- **Webフレームワーク**: Streamlit
- **データベース**: SQLite
- **データ分析**: pandas, numpy
- **可視化**: matplotlib, plotly
- **API連携**: requests

## インストール方法

### 必要条件

- Python 3.7以上
- pip (Pythonパッケージマネージャー)

### インストール手順

1. リポジトリをクローンまたはダウンロードします。

```bash
git clone https://github.com/yourusername/ortho-evidence.git
cd ortho-evidence
```

2. 必要なパッケージをインストールします。

```bash
pip install -r requirements.txt
```

## 使用方法

### システムの初期化

1. データベースの初期化とデータのセットアップを行います。

```bash
python main.py --all
```

これにより以下の処理が実行されます：
- SQLiteデータベースの作成
- 既存のCSVファイルからのデータインポート
- エビデンスデータの生成
- 結果データのCSVへのエクスポート

### Webアプリケーションの起動

```bash
python main.py
```

または直接Streamlitで起動:

```bash
streamlit run app.py
```

ブラウザが自動的に開き、アプリケーションにアクセスできます（通常はhttp://localhost:8501/）。

## アプリケーションの使い方

### レポート生成

1. 患者の年齢と性別を入力
2. 関連する歯列問題を選択
3. 必要に応じて追加メモを入力
4. 「レポート生成」ボタンをクリック
5. 生成されたレポートを確認し、HTML形式でダウンロード

### データ分析

- 「データ分析」ページでは、年齢別リスク、問題別効果、タイミングメリット、経済的影響などの各種データを視覚的に分析できます。
- 各グラフはインタラクティブに操作可能です。

### PubMed連携

- 「PubMed連携」ページでは、最新の歯科矯正研究論文を検索・取得できます。
- キーワード検索や一括取得機能を使ってデータベースを拡充できます。

## データ管理

### データのインポート

既存のデータをCSVファイルからインポートする場合：

```bash
python main.py --import
```

### エビデンスデータの生成

データベース内の論文からエビデンスを生成する場合：

```bash
python main.py --generate
```

### データのエクスポート

生成されたデータをCSVファイルにエクスポートする場合：

```bash
python main.py --export --output ./data
```

## システムの拡張

### 新しい歯列問題の追加

1. `dental_issues`テーブルに新しい問題を追加
2. 関連するキーワードを`issue_keywords`テーブルに追加

### 新しいエビデンスソースの追加

1. 新しいAPI連携モジュールを作成
2. インポートデータを標準形式に変換
3. `import_data()`関数を拡張

## トラブルシューティング

### PubMed APIの接続問題

- APIキーが必要な場合は、環境変数`NCBI_API_KEY`にAPIキーを設定します。
- リクエスト頻度が高すぎる場合は、`batch_pubmed_fetch.py`の`pause_seconds`の値を大きくします。

### データベースの問題

データベースに問題が発生した場合、リセットして再初期化できます：

```bash
python main.py --init
```

## ライセンス

このプロジェクトはMITライセンスの下で提供されています。詳細は[LICENSE](LICENSE)ファイルを参照してください。

## 貢献

バグの報告、機能リクエスト、プルリクエストは大歓迎です。貢献方法については[CONTRIBUTING.md](CONTRIBUTING.md)を参照してください。
