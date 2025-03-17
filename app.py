import streamlit as st

# ページ設定（このコードは必ず最初のStreamlit命令である必要があります）
st.set_page_config(
    page_title="歯科矯正エビデンス生成システム",
    page_icon="🦷",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 他のライブラリをインポート
import sys
import os
import pandas as pd
import numpy as np
from datetime import date
import re
import base64
import logging
import sqlite3
import json
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go

# カスタムモジュールをインポート
from evidence_processor import OrthoEvidenceProcessor

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ortho_evidence_app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ortho_evidence_app")

# デバッグ情報 - 本番環境では削除またはコメントアウトする
# st.write("Python version:", sys.version)
# st.write("Working directory contents:")
# st.write(os.listdir())

# セッション状態の初期化
if 'processor' not in st.session_state:
    try:
        # SQLiteデータベースへのパス
        db_path = "ortho_evidence.db"
        
        # データベースが存在するか確認
        db_exists = os.path.exists(db_path)
        
        # エビデンス処理モジュールの初期化
        processor = OrthoEvidenceProcessor(db_path)
        
        # 新しいデータベースの場合はスキーマを初期化
        if not db_exists:
            processor.initialize_db("db_schema.sql")
            st.info("新しいデータベースを初期化しました。データを読み込む必要があります。")
        
        st.session_state['processor'] = processor
    except Exception as e:
        st.error(f"データベース初期化エラー: {e}")
        logger.error(f"データベース初期化エラー: {e}")
# HTMLレポートを生成する関数
def generate_html_report(age, gender, issue_ids, issue_names, necessity_score, scenarios, economic_benefits, additional_notes=""):
    processor = st.session_state['processor']
    
    today = date.today().strftime("%Y年%m月%d日")
    
    # リスクプロファイルの取得
    risk_profiles_df = processor.get_age_risk_profiles()
    applicable_profile = risk_profiles_df[risk_profiles_df['age_threshold'] >= age].iloc[0] if not risk_profiles_df.empty else None
    
    # 問題別の効果データを取得
    effects_data = {}
    high_risks = []
    
    for issue_id in issue_ids:
        effects_df = processor.get_issue_treatment_effects(issue_id)
        if not effects_df.empty:
            effects_data[issue_id] = effects_df
            
            # 高リスク項目の抽出
            risk_effects = effects_df[effects_df['effect_direction'] == 'increase']
            for _, row in risk_effects.iterrows():
                if row['effect_value'] > 30:  # 30%以上のリスク増加を高リスクとする
                    high_risks.append(f"{row['issue_name_ja']}: {row['description_ja']}")
    
    # 矯正必要性スコアの色を設定
    if necessity_score["total_score"] >= 80:
        score_color = "#ff4444"  # 赤（緊急）
    elif necessity_score["total_score"] >= 60:
        score_color = "#ff8800"  # オレンジ（高）
    elif necessity_score["total_score"] >= 40:
        score_color = "#ffbb33"  # 黄色（中）
    else:
        score_color = "#00C851"  # 緑（低）
    
    # HTMLヘッダー
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>歯科矯正評価レポート</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }}
            h1, h2, h3 {{
                color: #0066cc;
                border-bottom: 1px solid #ddd;
                padding-bottom: 5px;
            }}
            h1 {{
                text-align: center;
                border-bottom: 2px solid #0066cc;
            }}
            .header-info {{
                text-align: center;
                margin-bottom: 20px;
            }}
            .section {{
                margin: 25px 0;
                padding: 0 15px;
            }}
            .risk-item {{
                margin: 10px 0;
                padding: 10px;
                border-left: 3px solid #ddd;
            }}
            .high-risk {{
                background-color: #ffeeee;
                border-left: 3px solid #ff4444;
            }}
            .warning {{
                background-color: #fff3cd;
                padding: 10px;
                border-left: 4px solid #ffc107;
                margin: 15px 0;
            }}
            .benefit {{
                background-color: #e8f4f8;
                padding: 10px;
                border-left: 4px solid #0099cc;
            }}
            .necessity-score {{
                text-align: center;
                margin: 30px auto;
                max-width: 400px;
            }}
            .score-display {{
                font-size: 36px;
                font-weight: bold;
                color: white;
                background-color: {score_color};
                border-radius: 50%;
                width: 120px;
                height: 120px;
                line-height: 120px;
                margin: 0 auto;
                text-align: center;
            }}
            .score-interpretation {{
                margin-top: 15px;
                font-weight: bold;
                font-size: 18px;
            }}
            .score-details {{
                display: flex;
                justify-content: space-between;
                margin-top: 20px;
                text-align: center;
            }}
            .score-component {{
                flex: 1;
                padding: 10px;
                border: 1px solid #ddd;
                border-radius: 5px;
                margin: 0 5px;
            }}
            .component-value {{
                font-weight: bold;
                font-size: 24px;
                color: #0066cc;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            th, td {{
                padding: 8px;
                text-align: left;
                border-bottom: 1px solid #ddd;
            }}
            th {{
                background-color: #f2f2f2;
            }}
            .comparison-table td {{
                vertical-align: top;
            }}
            .comparison-table td:first-child {{
                font-weight: bold;
                width: 20%;
            }}
            .comparison-good {{
                background-color: #e8f5e9;
                border-left: 4px solid #4caf50;
            }}
            .comparison-bad {{
                background-color: #ffebee;
                border-left: 4px solid #f44336;
            }}
            .economic-benefit {{
                display: flex;
                flex-direction: column;
                align-items: center;
                margin: 30px 0;
                padding: 20px;
                background-color: #e8f5e9;
                border-radius: 10px;
            }}
            .economic-numbers {{
                display: flex;
                justify-content: space-around;
                width: 100%;
                margin: 20px 0;
            }}
            .economic-item {{
                text-align: center;
                padding: 10px;
            }}
            .economic-value {{
                font-size: 24px;
                font-weight: bold;
                color: #2e7d32;
            }}
            .economic-label {{
                font-size: 14px;
                color: #555;
            }}
            .footer {{
                margin-top: 40px;
                border-top: 1px solid #ddd;
                padding-top: 10px;
                font-size: 0.8em;
                text-align: center;
                color: #666;
            }}
            .evidence-badge {{
                margin: 10px 0;
                padding: 10px;
                border-radius: 4px;
                background-color: #f9f9f9;
                border-left: 4px solid #0066cc;
            }}
            .evidence-level {{
                font-weight: bold;
                font-size: 14px;
            }}
            .evidence-type {{
                font-size: 12px;
                color: #666;
            }}
            @media print {{
                body {{
                    font-size: 12pt;
                }}
                .no-print {{
                    display: none;
                }}
                h1, h2, h3 {{
                    page-break-after: avoid;
                }}
                .section {{
                    page-break-inside: avoid;
                }}
            }}
        </style>
    </head>
    <body>
        <h1>歯科矯正評価レポート</h1>
        <div class="header-info">
            <p><strong>生成日:</strong> {today}</p>
            <p><strong>患者情報:</strong> {age}歳, {gender}</p>
    """
    
    # 追加メモがあれば追加
    if additional_notes:
        html += f'<p><strong>特記事項:</strong> {additional_notes}</p>'
    
    html += '</div>'
    
    # 矯正必要性スコア
    html += f'''
    <div class="section">
        <h2>矯正必要性スコア</h2>
        <div class="necessity-score">
            <div class="score-display">{necessity_score["total_score"]}</div>
            <div class="score-interpretation">{necessity_score["interpretation"]}</div>
            <div class="score-details">
                <div class="score-component">
                    <div class="component-value">{necessity_score["timing_score"]}</div>
                    <div>タイミング<br>スコア</div>
                </div>
                <div class="score-component">
                    <div class="component-value">{necessity_score["severity_score"]}</div>
                    <div>問題重大度<br>スコア</div>
                </div>
                <div class="score-component">
                    <div class="component-value">{necessity_score["risk_score"]}</div>
                    <div>将来リスク<br>スコア</div>
                </div>
            </div>
        </div>
    </div>
    '''
    
    # 高リスク項目のサマリー
    if high_risks:
        html += '''
        <div class="section">
            <h2>注意すべき高リスク項目</h2>
        '''
        for risk in high_risks:
            html += f'<div class="risk-item high-risk">{risk}</div>'
        html += '</div>'
    
    # 矯正タイミング評価
    timing_benefits = processor.get_age_timing_benefits()
    applicable_timing = None
    
    for _, row in timing_benefits.iterrows():
        if row['age_min'] <= age <= row['age_max']:
            applicable_timing = row
            break
    
    if applicable_timing is not None:
        html += f'''
        <div class="section">
            <h2>矯正タイミング評価</h2>
            <p><strong>現在の年齢グループ:</strong> {applicable_timing['age_group_ja']}</p>
            <p><strong>推奨レベル:</strong> {applicable_timing['recommendation_level']}</p>
            <p><strong>メリット:</strong> {applicable_timing['benefit_text_ja']}</p>
        '''
        
        # タイミング警告（年齢に基づくリスク）
        if applicable_profile is not None:
            html += f'<div class="warning"><strong>⚠️ 矯正タイミング警告:</strong> {applicable_profile["description_ja"]}</div>'
        
        html += '</div>'
    
    # 経済的メリット
    html += f'''
    <div class="section">
        <h2>歯列矯正の経済的メリット</h2>
        <div class="economic-benefit">
            <p>歯列矯正は健康への投資です。今矯正することで、生涯にわたって以下の経済的メリットが期待できます：</p>
            <div class="economic-numbers">
                <div class="economic-item">
                    <div class="economic-value">¥{economic_benefits["current_cost"]:,}</div>
                    <div class="economic-label">現在の矯正コスト</div>
                </div>
                <div class="economic-item">
                    <div class="economic-value">¥{economic_benefits["future_savings"]:,}</div>
                    <div class="economic-label">将来の医療費削減額</div>
                </div>
                <div class="economic-item">
                    <div class="economic-value">¥{economic_benefits["net_benefit"]:,}</div>
                    <div class="economic-label">生涯の純節約額</div>
                </div>
            </div>
            <p><strong>投資収益率: {economic_benefits["roi"]}%</strong>（矯正費用に対する長期的リターン）</p>
            <p>月あたり約 <strong>¥{economic_benefits["monthly_benefit"]:,}</strong> の医療費削減効果に相当します。</p>
        </div>
    </div>
    '''
    
    # 将来シナリオ比較
    filtered_scenarios = scenarios[scenarios.apply(lambda x: x['applies_to_age_min'] <= age <= x['applies_to_age_max'], axis=1)]
    
    if not filtered_scenarios.empty:
        html += '''
        <div class="section">
            <h2>将来シナリオ比較</h2>
            <p>矯正治療を受けた場合と受けなかった場合の将来予測：</p>
            <table class="comparison-table">
                <tr>
                    <th>期間</th>
                    <th>矯正した場合</th>
                    <th>矯正しなかった場合</th>
                </tr>
        '''
        
        for _, row in filtered_scenarios.iterrows():
            html += f'''
            <tr>
                <td>{row['timeframe']}</td>
                <td class="comparison-good">{row['with_ortho_text_ja']}</td>
                <td class="comparison-bad">{row['without_ortho_text_ja']}</td>
            </tr>
            '''
        
        html += '</table></div>'
    
    # 各歯列問題の詳細
    for i, issue_id in enumerate(issue_ids):
        issue_name = issue_names[i]
        effects_df = effects_data.get(issue_id)
        
        if effects_df is not None and not effects_df.empty:
            html += f'<div class="section"><h2>{issue_name}のリスク評価</h2>'
            
            # 効果・メリットの表示
            benefits = effects_df[effects_df['effect_direction'] == 'decrease']
            if not benefits.empty:
                html += '<div class="benefit"><strong>矯正による改善効果:</strong><ul>'
                for _, row in benefits.iterrows():
                    html += f'<li>{row["description_ja"]}</li>'
                html += '</ul></div>'
            
            # リスク項目の表示
            risks = effects_df[effects_df['effect_direction'] == 'increase']
            if not risks.empty:
                for _, row in risks.iterrows():
                    risk_class = "high-risk" if row['effect_value'] > 30 else "risk-item"
                    html += f'<div class="{risk_class}">{row["description_ja"]}</div>'
            
            html += '</div>'
    
    # フッター
    html += f'''
        <div class="footer">
            歯科エビデンス生成システム - レポート生成日: {today}
        </div>
        <div class="no-print" style="text-align: center; margin-top: 30px;">
            <button onclick="window.print();" style="padding: 10px 20px; background-color: #0066cc; color: white; border: none; border-radius: 4px; cursor: pointer;">
                印刷する / PDFとして保存
            </button>
        </div>
    </body>
    </html>
    '''
    
    return html

# HTMLをダウンロード可能にする関数
def get_html_download_link(html, filename):
    b64 = base64.b64encode(html.encode()).decode()
    href = f'<a href="data:text/html;base64,{b64}" download="{filename}" style="display: inline-block; padding: 10px 15px; background-color: #4CAF50; color: white; text-decoration: none; border-radius: 4px; margin: 10px 0;">HTMLレポートをダウンロード</a>'
    return href

# メインページ
def main():
    # タイトル表示
    st.title('🦷 歯科矯正エビデンス生成システム')
    st.write("患者の年齢と歯列問題に基づいたエビデンスレポートを生成します")
    
    # サイドバーに設定オプション
    with st.sidebar:
        st.header("設定")
        lang = st.selectbox("言語", ["日本語", "English"], index=0)
        include_citations = st.checkbox("論文引用を含める", value=True)
        show_ortho_timing = st.checkbox("矯正タイミング情報を表示", value=True)
        show_future_scenarios = st.checkbox("将来シナリオを表示", value=True)
        show_economic_benefits = st.checkbox("経済的メリットを表示", value=True)
        
        # データ管理セクション
        st.header("データ管理")
        
        # CSVファイルがあるか確認
        papers_csv_exists = os.path.exists('papers.csv')
        
        if papers_csv_exists:
            if st.button("論文データをインポート"):
                try:
                    processor = st.session_state['processor']
                    with st.spinner("論文データをインポート中..."):
                        count = processor.import_papers_from_csv()
                        st.success(f"{count}件の論文データをインポートしました")
                except Exception as e:
                    st.error(f"インポートエラー: {e}")
                    logger.error(f"インポートエラー: {e}", exc_info=True)
        else:
            st.warning("papers.csvファイルが見つかりません")
        
        # エビデンスデータの生成
        if st.button("エビデンスデータを生成"):
            try:
                processor = st.session_state['processor']
                with st.spinner("エビデンスデータを生成中..."):
                    summary = processor.generate_all_evidence_data()
                    
                    # 詳細な結果を表示
                    details = "\n".join([f"- {k}: {v}件" for k, v in summary.items()])
                    st.success(f"エビデンスデータを生成しました\n{details}")
            except Exception as e:
                st.error(f"エビデンス生成エラー: {e}")
                logger.error(f"エビデンス生成エラー: {e}", exc_info=True)
        
        # CSVエクスポート
        if st.button("データをCSVにエクスポート"):
            try:
                processor = st.session_state['processor']
                with st.spinner("CSVファイルを生成中..."):
                    count = processor.export_to_csv()
                    st.success(f"{count}個のCSVファイルをエクスポートしました")
            except Exception as e:
                st.error(f"エクスポートエラー: {e}")
                logger.error(f"エクスポートエラー: {e}", exc_info=True)
        
        # データベースリセット（危険な操作）
        with st.expander("危険な操作"):
            st.warning("以下の操作はデータを完全に削除します。注意してください。")
            if st.button("データベースをリセット", key="reset_db"):
                try:
                    processor = st.session_state['processor']
                    with st.spinner("データベースをリセット中..."):
                        processor.reset_database()
                        st.success("データベースをリセットしました")
                except Exception as e:
                    st.error(f"リセットエラー: {e}")
                    logger.error(f"リセットエラー: {e}", exc_info=True)
    
    # メインコンテンツ
    col1, col2 = st.columns([2, 1])
    
    try:
        processor = st.session_state['processor']
        
        # 歯列問題リストを取得
        dental_issues_df = processor.get_dental_issues()
        
        with col1:
            # 入力フォーム
            with st.form("input_form"):
                age = st.number_input('患者年齢', min_value=1, max_value=100, value=30)
                gender = st.selectbox('性別', ['男性', '女性', 'その他'])
                
                # 歯列問題の選択
                issue_options = [(row['issue_id'], row['issue_name_ja']) for _, row in dental_issues_df.iterrows()]
                selected_issues = st.multiselect('歯列問題', options=issue_options, format_func=lambda x: x[1])
                
                additional_notes = st.text_area("追加メモ", placeholder="患者の特記事項があれば入力してください")
                submitted = st.form_submit_button("レポート生成")
        
        with col2:
            # データ統計情報
            st.subheader("エビデンスデータ統計")
            
            try:
                # 論文数の取得
                conn = sqlite3.connect(processor.db_path)
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM research_papers")
                papers_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM research_findings")
                findings_count = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM dental_issues")
                issues_count = cursor.fetchone()[0]
                
                conn.close()
                
                # 統計情報の表示
                st.metric("登録論文数", papers_count)
                st.metric("抽出知見数", findings_count)
                st.metric("歯列問題数", issues_count)
                
                # 歯列問題の分布グラフ
                if not dental_issues_df.empty and papers_count > 0:
                    st.subheader("問題別重大度スコア")
                    
                    fig = px.bar(
                        dental_issues_df, 
                        x='issue_name_ja', 
                        y='severity_base_score',
                        color='severity_base_score',
                        color_continuous_scale='RdYlBu_r',
                        labels={'issue_name_ja': '歯列問題', 'severity_base_score': '重大度スコア'}
                    )
                    fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
                    st.plotly_chart(fig, use_container_width=True)
            
            except Exception as e:
                st.error(f"データ統計取得エラー: {e}")
                logger.error(f"データ統計取得エラー: {e}", exc_info=True)
        
        # レポート生成
        if submitted:
            if not selected_issues:
                st.error("少なくとも1つの歯列問題を選択してください")
            else:
                issue_ids = [issue[0] for issue in selected_issues]
                issue_names = [issue[1] for issue in selected_issues]
                
                st.success(f"{len(issue_ids)}つの歯列問題に基づいたレポートを生成しました")
                
                # 矯正必要性スコアの計算
                necessity_score = processor.calculate_ortho_necessity_score(age, issue_ids)
                
                # 経済的メリットの計算
                economic_benefits = processor.get_economic_impact(age)
                
                # 将来シナリオの取得
                scenarios = processor.get_future_scenarios(age=age)
                
                # エビデンスレポートの表示
                st.subheader("矯正必要性スコア")
                
                # スコア表示用の列
                score_cols = st.columns(4)
                with score_cols[0]:
                    st.metric("総合スコア", necessity_score['total_score'])
                with score_cols[1]:
                    st.metric("タイミングスコア", necessity_score['timing_score'])
                with score_cols[2]:
                    st.metric("重大度スコア", necessity_score['severity_score'])
                with score_cols[3]:
                    st.metric("将来リスクスコア", necessity_score['risk_score'])
                
                st.info(necessity_score['interpretation'])
                
                # 各問題の詳細を表示
                st.subheader("選択された歯列問題の詳細")
                
                for i, issue_id in enumerate(issue_ids):
                    with st.expander(f"{issue_names[i]}の詳細"):
                        # 効果データの取得と表示
                        effects_df = processor.get_issue_treatment_effects(issue_id)
                        
                        if not effects_df.empty:
                            # 効果とリスクに分ける
                            benefits = effects_df[effects_df['effect_direction'] == 'decrease']
                            risks = effects_df[effects_df['effect_direction'] == 'increase']
                            
                            if not benefits.empty:
                                st.markdown("**矯正による改善効果:**")
                                for _, row in benefits.iterrows():
                                    st.success(row['description_ja'])
                            
                            if not risks.empty:
                                st.markdown("**放置した場合のリスク:**")
                                for _, row in risks.iterrows():
                                    severity = "error" if row['effect_value'] > 30 else "warning"
                                    getattr(st, severity)(row['description_ja'])
                        else:
                            st.warning("この問題に関するエビデンスデータが不足しています")
                
                # HTML版レポート生成
                html_report = generate_html_report(
                    age, gender, issue_ids, issue_names, 
                    necessity_score, scenarios, economic_benefits,
                    additional_notes
                )
                
                # ダウンロードボタン
                st.markdown("<h3>レポートのダウンロード</h3>", unsafe_allow_html=True)
                st.write("以下のいずれかの形式でレポートをダウンロードできます：")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # HTML形式
                    st.markdown(get_html_download_link(html_report, f"歯科矯正評価_{date.today().strftime('%Y%m%d')}.html"), unsafe_allow_html=True)
                    st.write("※HTMLファイルをブラウザで開き、印刷機能からPDFとして保存できます")
                
                with col2:
                    # JSON形式（データのみ）
                    report_data = {
                        "patient": {
                            "age": age,
                            "gender": gender,
                            "issues": issue_names,
                            "notes": additional_notes
                        },
                        "necessity_score": necessity_score,
                        "economic_benefits": economic_benefits
                    }
                    
                    json_str = json.dumps(report_data, ensure_ascii=False, indent=2)
                    st.download_button("JSONデータをダウンロード", json_str, f"歯科矯正評価_{date.today().strftime('%Y%m%d')}.json")
    
    except Exception as e:
        st.error(f"システムエラーが発生しました: {e}")
        logger.error(f"システムエラー: {e}", exc_info=True)
        st.error("データベースへの接続に問題があるか、データが不足しています。サイドバーの「エビデンスデータを生成」ボタンを押してデータを作成してください。")

# データ分析ページ
def data_analysis():
    st.title("データ分析ダッシュボード")
    st.write("歯科矯正エビデンスの分析と可視化")
    
    try:
        processor = st.session_state['processor']
        
        # 分析タイプの選択
        analysis_type = st.selectbox(
            "分析タイプ",
            ["年齢別リスク", "問題別効果", "タイミングメリット", "経済的影響"]
        )
        
        if analysis_type == "年齢別リスク":
            # 年齢別リスクの分析
            risk_profiles = processor.get_age_risk_profiles()
            
            if not risk_profiles.empty:
                st.subheader("年齢別の歯列矯正リスクプロファイル")
                
                # リスク値のグラフ
                fig = px.line(
                    risk_profiles, 
                    x='age_threshold', 
                    y='risk_value',
                    markers=True,
                    line_shape='spline',
                    labels={'age_threshold': '年齢', 'risk_value': 'リスク値 (%)'},
                    title="年齢に伴うリスク増加"
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
                
                # リスク説明の表示
                st.subheader("各年齢閾値でのリスク説明")
                for _, row in risk_profiles.iterrows():
                    st.markdown(f"**{row['age_threshold']}歳の閾値:**")
                    st.info(row['description_ja'])
            else:
                st.warning("年齢別リスクデータがありません。「エビデンスデータを生成」ボタンを押してデータを作成してください。")
        
        elif analysis_type == "問題別効果":
            # 問題別効果の分析
            dental_issues = processor.get_dental_issues()
            
            if not dental_issues.empty:
                selected_issue = st.selectbox(
                    "歯列問題を選択",
                    [(row['issue_id'], row['issue_name_ja']) for _, row in dental_issues.iterrows()],
                    format_func=lambda x: x[1]
                )
                
                if selected_issue:
                    issue_id, issue_name = selected_issue
                    effects_df = processor.get_issue_treatment_effects(issue_id)
                    
                    if not effects_df.empty:
                        st.subheader(f"{issue_name}の矯正効果分析")
                        
                        # 効果のグラフ化
                        effects_df['abs_effect'] = effects_df['effect_value'].abs()
                        effects_df['effect_type'] = effects_df.apply(
                            lambda x: '改善効果' if x['effect_direction'] == 'decrease' else 'リスク',
                            axis=1
                        )
                        
                        fig = px.bar(
                            effects_df,
                            x='effect_category',
                            y='abs_effect',
                            color='effect_type',
                            color_discrete_map={'改善効果': '#4CAF50', 'リスク': '#F44336'},
                            labels={'effect_category': 'カテゴリ', 'abs_effect': '効果の大きさ (%)'},
                            title=f"{issue_name}に関連する効果とリスク"
                        )
                        fig.update_layout(height=400)
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # 効果の詳細表示
                        st.subheader("効果の詳細")
                        
                        benefits = effects_df[effects_df['effect_direction'] == 'decrease']
                        risks = effects_df[effects_df['effect_direction'] == 'increase']
                        
                        if not benefits.empty:
                            st.markdown("**矯正による改善効果:**")
                            for _, row in benefits.iterrows():
                                st.success(row['description_ja'])
                        
                        if not risks.empty:
                            st.markdown("**放置した場合のリスク:**")
                            for _, row in risks.iterrows():
                                st.error(row['description_ja'])
                    else:
                        st.warning(f"{issue_name}に関するエビデンスデータがありません")
            else:
                st.warning("歯列問題データがありません。「エビデンスデータを生成」ボタンを押してデータを作成してください。")
        
        elif analysis_type == "タイミングメリット":
            # タイミングメリットの分析
            timing_benefits = processor.get_age_timing_benefits()
            
            if not timing_benefits.empty:
                st.subheader("年齢グループ別の矯正タイミング効果")
                
                # タイミングスコアのグラフ
                fig = px.bar(
                    timing_benefits,
                    x='age_group_ja',
                    y='timing_score',
                    color='recommendation_level',
                    labels={'age_group_ja': '年齢グループ', 'timing_score': 'タイミングスコア'},
                    title="年齢グループごとの矯正タイミング適正度"
                )
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
                
                # タイミングメリットの詳細
                st.subheader("各年齢グループのタイミングメリット")
                for _, row in timing_benefits.iterrows():
                    with st.expander(f"{row['age_group_ja']} ({row['recommendation_level']})"):
                        st.markdown(f"**推奨レベル:** {row['recommendation_level']}")
                        st.markdown(f"**タイミングスコア:** {row['timing_score']}/100")
                        st.info(row['benefit_text_ja'])
            else:
                st.warning("タイミングメリットデータがありません。「エビデンスデータを生成」ボタンを押してデータを作成してください。")
        
        elif analysis_type == "経済的影響":
            # 経済的影響の分析
            conn = sqlite3.connect(processor.db_path)
            economic_impacts = pd.read_sql_query("SELECT * FROM economic_impacts", conn)
            conn.close()
            
            if not economic_impacts.empty:
                st.subheader("矯正治療の経済的影響分析")
                
                # 経済的メリットのグラフ
                economic_impacts['net_benefit'] = economic_impacts['future_savings'] - economic_impacts['current_cost']
                
                # 棒グラフで表示
                fig = go.Figure()
                
                fig.add_trace(go.Bar(
                    x=economic_impacts['age_group_ja'],
                    y=economic_impacts['current_cost'],
                    name='現在の矯正コスト',
                    marker_color='#FF9800'
                ))
                
                fig.add_trace(go.Bar(
                    x=economic_impacts['age_group_ja'],
                    y=economic_impacts['future_savings'],
                    name='将来の医療費削減額',
                    marker_color='#4CAF50'
                ))
                
                fig.update_layout(
                    title='年齢グループ別の矯正コストと将来の節約額',
                    xaxis_title='年齢グループ',
                    yaxis_title='金額 (円)',
                    barmode='group',
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # ROIのグラフ
                fig2 = px.line(
                    economic_impacts,
                    x='age_group_ja',
                    y='roi',
                    markers=True,
                    labels={'age_group_ja': '年齢グループ', 'roi': '投資収益率 (%)'},
                    title="年齢グループ別の投資収益率（ROI）"
                )
                fig2.update_layout(height=350)
                st.plotly_chart(fig2, use_container_width=True)
                
                # 経済的メリットの詳細
                st.subheader("各年齢グループの経済的詳細")
                for _, row in economic_impacts.iterrows():
                    with st.expander(f"{row['age_group_ja']}"):
                        st.markdown(f"**現在の矯正コスト:** ¥{row['current_cost']:,}")
                        st.markdown(f"**将来の医療費削減額:** ¥{row['future_savings']:,}")
                        st.markdown(f"**純節約額:** ¥{row['future_savings'] - row['current_cost']:,}")
                        st.markdown(f"**投資収益率 (ROI):** {row['roi']:.1f}%")
            else:
                st.warning("経済的影響データがありません。「エビデンスデータを生成」ボタンを押してデータを作成してください。")
    
    except Exception as e:
        st.error(f"分析エラー: {e}")
        logger.error(f"分析エラー: {e}", exc_info=True)
        st.error("データベースへの接続に問題があるか、データが不足しています。サイドバーの「エビデンスデータを生成」ボタンを押してデータを作成してください。")

# PubMed連携ページ
def pubmed_integration():
    st.title("PubMed論文データ連携")
    st.write("PubMed APIを使用して最新の研究論文を取得・分類します")
    
    # PubMed API関連のモジュールをインポート
    api_modules_imported = False
    try:
        from pubmed_api import fetch_pubmed_studies, get_pubmed_article_details, update_papers_csv
        api_modules_imported = True
    except ImportError as e:
        st.error(f"pubmed_api.pyモジュールのインポートエラー: {str(e)}")
        api_modules_imported = False
    
    if not api_modules_imported:
        st.error("PubMed API連携モジュールがインポートできません。pubmed_api.pyファイルが存在するか確認してください。")
        return
    
    # 検索フォーム
    with st.form("pubmed_search_form"):
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            search_keyword = st.text_input("検索キーワード", "malocclusion OR orthodontic")
        with col2:
            max_results = st.number_input("最大取得件数", min_value=1, max_value=50, value=10)
        with col3:
            days_recent = st.slider("期間（日）", 30, 365, 90)
        
        search_button = st.form_submit_button("論文を検索")
    
    if search_button:
        with st.spinner("PubMedから論文を検索中..."):
            # 検索実行
            search_results = fetch_pubmed_studies(search_keyword, max_results, days_recent)
            
            if 'esearchresult' in search_results and 'idlist' in search_results['esearchresult']:
                pmid_list = search_results['esearchresult']['idlist']
                
                if pmid_list:
                    st.success(f"{len(pmid_list)}件の論文が見つかりました")
                    
                    # 論文詳細の取得
                    with st.spinner("論文の詳細情報を取得中..."):
                        articles = get_pubmed_article_details(pmid_list)
                        
                        if articles:
                            # 論文一覧を表示
                            st.subheader("取得した論文")
                            
                            for i, article in enumerate(articles):
                                with st.expander(f"{i+1}. {article.get('title', '不明')}"):
                                    st.markdown(f"**著者:** {article.get('authors', '不明')}")
                                    st.markdown(f"**掲載誌:** {article.get('journal', '不明')} ({article.get('publication_year', '不明')})")
                                    st.markdown(f"**DOI:** {article.get('doi', '不明')}")
                                    st.markdown(f"**研究タイプ:** {article.get('study_type', '不明')}")
                                    
                                    # エビデンスレベルの表示
                                    if 'evidence_level' in article:
                                        evidence_level = article['evidence_level']
                                        evidence_colors = {
                                            '1a': '#4CAF50', '1b': '#8BC34A',
                                            '2a': '#FFC107', '2b': '#FF9800',
                                            '3': '#FF5722', '4': '#F44336',
                                            '5': '#9E9E9E'
                                        }
                                        evidence_texts = {
                                            '1a': 'メタ分析/システマティックレビュー',
                                            '1b': 'ランダム化比較試験',
                                            '2a': 'コホート研究',
                                            '2b': '症例対照研究/臨床試験',
                                            '3': '横断研究/実験研究',
                                            '4': '症例報告/症例シリーズ',
                                            '5': '専門家意見/不明'
                                        }
                                        
                                        st.markdown(
                                            f"**エビデンスレベル:** <span style='color:{evidence_colors.get(evidence_level, '#9E9E9E')};'>"
                                            f"レベル {evidence_level} ({evidence_texts.get(evidence_level, '不明')})</span>",
                                            unsafe_allow_html=True
                                        )
                                    
                                    # 抄録の表示
                                    if 'abstract' in article and article['abstract']:
                                        with st.expander("抄録"):
                                            st.write(article['abstract'])
                                    
                                    # PubMedリンク
                                    if 'url' in article:
                                        st.markdown(f"[PubMedで表示]({article['url']})")
                            
                            # CSVに保存するかの確認
                            if st.button("これらの論文をデータベースに追加"):
                                with st.spinner("論文をデータベースに追加中..."):
                                    try:
                                        # プロセッサを使用してCSVを更新
                                        processor = st.session_state['processor']
                                        
                                        # 論文の直接挿入
                                        count = 0
                                        for article in articles:
                                            paper_id = processor._insert_paper(article)
                                            if paper_id:
                                                count += 1
                                        
                                        processor.conn.commit()
                                        st.success(f"{count}件の論文をデータベースに追加しました")
                                        
                                        # エビデンスの再生成を推奨
                                        st.info("論文の追加後は、サイドバーの「エビデンスデータを生成」ボタンを押してエビデンスデータを更新することをお勧めします。")
                                    except Exception as e:
                                        st.error(f"データベース追加エラー: {e}")
                                        logger.error(f"データベース追加エラー: {e}", exc_info=True)
                        else:
                            st.warning("論文の詳細情報を取得できませんでした")
                else:
                    st.warning("該当する論文が見つかりませんでした")
            else:
                st.error("PubMedの検索に失敗しました")
    
    # バッチ処理セクション
    st.subheader("論文の一括取得")
    st.write("複数のキーワードを使用して論文を一括取得します")
    
    with st.form("pubmed_batch_form"):
        # キーワードの設定
        default_keywords = """dental crowding evidence
open bite treatment orthodontic
deep bite treatment orthodontic
crossbite treatment evidence
overjet treatment orthodontic
underbite treatment evidence"""
        
        keywords_text = st.text_area(
            "検索キーワード（1行に1つ）",
            value=default_keywords,
            height=150
        )
        
        col1, col2 = st.columns(2)
        with col1:
            batch_max_results = st.number_input("キーワードごとの最大取得数", min_value=1, max_value=30, value=5)
        with col2:
            batch_days_recent = st.slider("期間（日）", 30, 365, 180, key="batch_days")
        
        batch_button = st.form_submit_button("一括取得開始")
    
    if batch_button:
        keywords = [k.strip() for k in keywords_text.split('\n') if k.strip()]
        
        if keywords:
            st.write(f"**{len(keywords)}個**のキーワードを使用して、キーワードごとに最大**{batch_max_results}件**の論文を取得します")
            
            # 進捗表示用のプレースホルダー
            progress_placeholder = st.empty()
            log_placeholder = st.empty()
            
            with st.spinner("論文データ取得中..."):
                # 進捗バーの初期化
                progress_bar = progress_placeholder.progress(0)
                
                # カウンター初期化
                total_articles = 0
                total_new_articles = 0
                
                try:
                    processor = st.session_state['processor']
                    
                    # キーワードごとに処理
                    for i, keyword in enumerate(keywords):
                        # 進捗更新
                        progress = (i / len(keywords))
                        progress_bar.progress(progress)
                        
                        # キーワード表示
                        log_placeholder.markdown(f"**処理中:** '{keyword}' ({i+1}/{len(keywords)})")
                        
                        try:
                            # 検索実行
                            search_results = fetch_pubmed_studies(keyword, batch_max_results, batch_days_recent)
                            
                            if 'esearchresult' in search_results and 'idlist' in search_results['esearchresult']:
                                pmid_list = search_results['esearchresult']['idlist']
                                
                                if pmid_list:
                                    log_placeholder.markdown(f"  **{len(pmid_list)}件**の論文が見つかりました")
                                    
                                    # 論文詳細の取得
                                    articles = get_pubmed_article_details(pmid_list)
                                    
                                    # データベースに追加
                                    if articles:
                                        # 更新前のサイズを記録
                                        conn = sqlite3.connect(processor.db_path)
                                        cursor = conn.cursor()
                                        cursor.execute("SELECT COUNT(*) FROM research_papers")
                                        old_size = cursor.fetchone()[0]
                                        conn.close()
                                        
                                        # 論文の挿入
                                        new_count = 0
                                        for article in articles:
                                            paper_id = processor._insert_paper(article)
                                            if paper_id:
                                                new_count += 1
                                        
                                        # 変更を保存
                                        processor.conn.commit()
                                        
                                        total_articles += len(articles)
                                        total_new_articles += new_count
                                        
                                        log_placeholder.markdown(f"  **{new_count}件**の新規論文をデータベースに追加しました")
                                    else:
                                        log_placeholder.warning("  論文詳細の取得に失敗しました")
                                else:
                                    log_placeholder.info("  該当する論文が見つかりませんでした")
                            else:
                                log_placeholder.error(f"  検索結果が無効な形式です")
                        
                        except Exception as e:
                            log_placeholder.error(f"  エラーが発生しました: {e}")
                            logger.error(f"バッチ処理エラー: {e}", exc_info=True)
                        
                        # API制限対策の待機（最後のキーワードでは不要）
                        if i < len(keywords) - 1:
                            import time
                            time.sleep(2)  # 2秒待機
                    
                    # 完了
                    progress_bar.progress(1.0)
                    
                    # 成功メッセージ
                    st.success(f"データ取得が完了しました! {total_new_articles}件の新しい論文がデータベースに追加されました。")
                    
                    # エビデンスの再生成を推奨
                    st.info("論文の追加後は、サイドバーの「エビデンスデータを生成」ボタンを押してエビデンスデータを更新することをお勧めします。")
                
                except Exception as e:
                    st.error(f"一括取得エラー: {e}")
                    logger.error(f"一括取得エラー: {e}", exc_info=True)
        else:
            st.error("キーワードが指定されていません")

# マルチページアプリケーション
def run():
    # サイドバーにページ選択を追加
    st.sidebar.title("ナビゲーション")
    page = st.sidebar.radio(
        "ページ選択",
        ["レポート生成", "データ分析", "PubMed連携"]
    )
    
    # 選択したページを表示
    if page == "レポート生成":
        main()
    elif page == "データ分析":
        data_analysis()
    elif page == "PubMed連携":
        pubmed_integration()

if __name__ == "__main__":
    run()
