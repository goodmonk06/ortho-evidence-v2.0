import requests
import pandas as pd
import xml.etree.ElementTree as ET
import re
import time
import os
import streamlit as st

# APIキーを取得する関数
def get_api_key():
    """
    APIキーを環境変数またはStreamlitシークレットから取得します。
    
    Returns:
    --------
    str or None
        APIキー、見つからない場合はNone
    """
    # 1. Streamlit Cloudsのシークレットから取得を試みる
    try:
        return st.secrets.get("NCBI_API_KEY")
    except:
        pass
    
    # 2. 環境変数から取得を試みる
    return os.environ.get("NCBI_API_KEY")

def fetch_pubmed_studies(keywords, max_results=20, days_recent=90):
    """
    PubMed APIを使用して、指定したキーワードに関連する最新の矯正歯科論文を検索します。
    
    Parameters:
    -----------
    keywords : str
        検索キーワード (例: "malocclusion", "crowding", "open bite")
    max_results : int
        取得する最大論文数
    days_recent : int
        何日前までの論文を検索するか
        
    Returns:
    --------
    dict
        検索結果を含む辞書
    """
    # PubMed検索用のベースURL
    base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    
    # APIキーの取得
    api_key = get_api_key()
    
    # リクエストパラメータ設定
    params = {
        'db': 'pubmed',
        'term': f'({keywords}) AND ("orthodontics"[MeSH] OR "orthodontic"[Text Word])',
        'retmax': max_results,
        'sort': 'relevance',
        'reldate': days_recent,
        'datetype': 'pdat',
        'retmode': 'json',
    }
    
    # APIキーがある場合は追加
    if api_key:
        params['api_key'] = api_key
    
    try:
        # PubMed APIへリクエスト送信
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # ステータスコードの確認
        
        # JSON形式で結果を返す
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"PubMed APIリクエストエラー: {e}")
        return {'esearchresult': {'idlist': []}}

def get_pubmed_article_details(pmid_list):
    """
    PubMed IDリストから論文の詳細情報を取得します。
    
    Parameters:
    -----------
    pmid_list : list
        PubMed ID（PMID）のリスト
        
    Returns:
    --------
    list of dict
        各論文の詳細情報を含む辞書のリスト
    """
    if not pmid_list:
        return []
    
    # PubMed詳細取得用のベースURL
    fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    
    # カンマ区切りのPMIDリスト作成
    pmids = ','.join(pmid_list)
    
    # APIキーの取得
    api_key = get_api_key()
    
    # リクエストパラメータ設定
    params = {
        'db': 'pubmed',
        'id': pmids,
        'retmode': 'xml',
    }
    
    # APIキーがある場合は追加
    if api_key:
        params['api_key'] = api_key
    
    try:
        # PubMed APIへリクエスト送信
        response = requests.get(fetch_url, params=params)
        response.raise_for_status()
        
        # XMLを解析
        root = ET.fromstring(response.content)
        
        articles = []
        for article in root.findall('.//PubmedArticle'):
            try:
                # タイトル取得
                title_element = article.find('.//ArticleTitle')
                title = title_element.text if title_element is not None else "タイトル不明"
                
                # 抄録取得
                abstract_texts = article.findall('.//AbstractText')
                abstract = ' '.join([abstract_text.text for abstract_text in abstract_texts if abstract_text.text]) if abstract_texts else "抄録なし"
                
                # DOI取得
                doi_element = article.find('.//ArticleId[@IdType="doi"]')
                doi = doi_element.text if doi_element is not None else "DOI不明"
                
                # 出版年取得
                pub_date = article.find('.//PubDate')
                year_element = pub_date.find('./Year')
                year = year_element.text if year_element is not None else "年不明"
                
                # 著者取得
                authors_list = article.findall('.//Author')
                authors = []
                for author in authors_list:
                    last_name = author.find('./LastName')
                    fore_name = author.find('./ForeName')
                    if last_name is not None and fore_name is not None:
                        authors.append(f"{last_name.text} {fore_name.text}")
                    elif last_name is not None:
                        authors.append(last_name.text)
                authors_str = ', '.join(authors) if authors else "著者不明"
                
                # キーワード取得
                keywords = []
                keyword_elements = article.findall('.//Keyword')
                for keyword in keyword_elements:
                    if keyword.text:
                        keywords.append(keyword.text)
                keywords_str = ', '.join(keywords) if keywords else "キーワードなし"
                
                # MeSH用語取得
                mesh_terms = []
                mesh_elements = article.findall('.//MeshHeading/DescriptorName')
                for mesh in mesh_elements:
                    if mesh.text:
                        mesh_terms.append(mesh.text)
                mesh_str = ', '.join(mesh_terms) if mesh_terms else "MeSH用語なし"
                
                # 研究タイプの推測（タイトルと抄録から）
                study_type = determine_study_type(title, abstract)
                
                # PMIDの取得
                pmid_element = article.find('.//PMID')
                pmid = pmid_element.text if pmid_element is not None else "PMID不明"
                
                # ジャーナル名取得
                journal_element = article.find('.//Journal/Title')
                journal = journal_element.text if journal_element is not None else "ジャーナル不明"
                
                # サンプルサイズ抽出
                sample_size = extract_sample_size(abstract)
                
                # 論文の詳細情報を辞書として保存
                articles.append({
                    'pmid': pmid,
                    'title': title,
                    'abstract': abstract,
                    'doi': doi,
                    'publication_year': year,
                    'authors': authors_str,
                    'keywords': keywords_str,
                    'mesh_terms': mesh_str,
                    'study_type': study_type,
                    'journal': journal,
                    'sample_size': sample_size,
                    'confidence_interval': extract_confidence_interval(abstract),
                    'age_group': determine_age_group(abstract),
                    'url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                })
            except Exception as e:
                print(f"論文データの解析エラー: {e}")
                continue
        
        return articles
        
    except requests.exceptions.RequestException as e:
        print(f"PubMed 詳細取得APIエラー: {e}")
        return []

# 以下の関数は変更なし
def determine_study_type(title, abstract):
    """
    タイトルと抄録から研究タイプを推測します。
    """
    text = (title + " " + abstract).lower()
    
    # メタ分析、システマティックレビュー
    if any(term in text for term in ["meta-analysis", "systematic review", "meta analysis"]):
        return "meta-analysis"
    
    # ランダム化比較試験
    elif any(term in text for term in ["randomized controlled trial", "rct", "randomised"]):
        return "randomized-controlled-trial"
    
    # コホート研究
    elif any(term in text for term in ["cohort", "prospective study", "longitudinal study", "follow-up study"]):
        return "cohort-study"
    
    # 症例対照研究
    elif any(term in text for term in ["case-control", "case control"]):
        return "case-control"
    
    # 横断研究
    elif any(term in text for term in ["cross-sectional", "prevalence study"]):
        return "cross-sectional"
    
    # 症例報告
    elif any(term in text for term in ["case report", "case series"]):
        return "case-report"
    
    # 臨床試験
    elif any(term in text for term in ["clinical trial", "intervention study"]):
        return "clinical-trial"
    
    # 実験研究
    elif any(term in text for term in ["in vitro", "laboratory", "experimental study"]):
        return "experimental-study"
    
    # デフォルト
    return "unspecified-study"

def map_study_type_to_evidence_level(study_type):
    """
    研究タイプからエビデンスレベルへのマッピング
    """
    evidence_levels = {
        "meta-analysis": "1a",  # 最高レベル: メタ分析、システマティックレビュー
        "randomized-controlled-trial": "1b",  # 高レベル: ランダム化比較試験
        "cohort-study": "2a",  # 中-高レベル: コホート研究
        "case-control": "2b",  # 中レベル: 症例対照研究
        "cross-sectional": "3",  # 中-低レベル: 横断研究
        "clinical-trial": "2b",  # 中レベル: 臨床試験
        "experimental-study": "3",  # 中-低レベル: 実験研究
        "case-report": "4",  # 低レベル: 症例報告
        "unspecified-study": "5"  # 不明: 専門家意見など
    }
    
    return evidence_levels.get(study_type, "5")

def classify_dental_issue(title, abstract, keywords, mesh_terms):
    """
    論文タイトル、抄録、キーワード、MeSH用語から歯列問題を分類します。
    """
    text = (title + " " + abstract + " " + keywords + " " + mesh_terms).lower()
    
    # 日本語の歯列問題とその英語表現のマッピング
    dental_issues = {
        "叢生": ["crowding", "dental crowding", "malocclusion", "tooth crowding"],
        "開咬": ["open bite", "anterior open bite", "open occlusion"],
        "過蓋咬合": ["deep bite", "overbite", "deep overbite"],
        "交叉咬合": ["crossbite", "cross bite", "cross-bite", "posterior crossbite"],
        "上顎前突": ["overjet", "maxillary protrusion", "class ii malocclusion", "maxillary prognathism"],
        "下顎前突": ["underbite", "mandibular prognathism", "class iii malocclusion", "mandibular protrusion"]
    }
    
    # テキスト内の表現に基づいて歯列問題を分類
    for issue, terms in dental_issues.items():
        if any(term in text for term in terms):
            return issue
    
    # デフォルト
    return "その他の歯列問題"

def extract_sample_size(abstract):
    """
    抄録からサンプルサイズを抽出する試みをします。
    """
    if not abstract:
        return None
    
    # サンプルサイズを示す一般的なパターン
    patterns = [
        r'(?:total of|included|enrolled|analyzed|comprising|consisted of|sample of|n\s*=\s*)(\d+)(?:\s+(?:patients|subjects|participants|children|adults|individuals))',
        r'(\d+)(?:\s+(?:patients|subjects|participants|children|adults|individuals))(?:\s+were\s+(?:included|enrolled|studied))',
        r'sample(?:\s+size)?(?:\s+of)?(?:\s+was)?(?:\s+were)?\s*(?::|was|=)\s*(\d+)',
        r'(?:a|the)\s+(?:total\s+)?(?:of\s+)?(\d+)\s+(?:patients|subjects|participants|children|adults|individuals)'
    ]
    
    for pattern in patterns:
        matches = re.search(pattern, abstract, re.IGNORECASE)
        if matches:
            try:
                return int(matches.group(1))
            except (IndexError, ValueError):
                continue
    
    return None

def extract_confidence_interval(abstract):
    """
    抄録から信頼区間を抽出する試みをします。
    """
    if not abstract:
        return None
    
    # 信頼区間を示す一般的なパターン
    patterns = [
        r'(?:95%\s+CI|95%\s+confidence\s+interval)(?:\s+of)?(?:\s+was)?(?:\s+:)?\s*(?:\[|\()?(\d+\.?\d*)[^\d]+(\d+\.?\d*)(?:\]|\))',
        r'(?:\[|\()(\d+\.?\d*)[^\d]+(\d+\.?\d*)(?:\]|\))(?:\s+95%\s+CI)'
    ]
    
    for pattern in patterns:
        matches = re.search(pattern, abstract, re.IGNORECASE)
        if matches:
            try:
                lower = matches.group(1)
                upper = matches.group(2)
                return f"95% CI: {lower}-{upper}"
            except (IndexError, ValueError):
                continue
    
    return None

def determine_age_group(abstract):
    """
    抄録から年齢グループを判定します。
    """
    if not abstract:
        return "全年齢"
    
    abstract_lower = abstract.lower()
    
    # 小児を示す表現
    children_terms = ["children", "child", "pediatric", "paediatric", "young", "deciduous dentition", "mixed dentition", "primary dentition"]
    
    # 青年を示す表現
    adolescent_terms = ["adolescent", "adolescence", "teenager", "young adult", "young people"]
    
    # 成人を示す表現
    adult_terms = ["adult", "middle-aged", "middle aged"]
    
    # 高齢者を示す表現
    elderly_terms = ["elderly", "older adult", "geriatric", "older people", "senior"]
    
    # 年齢の範囲を探す
    age_patterns = [
        r'age(?:d|s)?\s+(?:between|from|of|range)?\s*(\d+)(?:\s*-\s*|\s+to\s+)(\d+)(?:\s+years)?',
        r'(\d+)(?:\s*-\s*|\s+to\s+)(\d+)(?:\s+years?\s+old|\s+years?\s+of\s+age)',
        r'mean\s+age\s+(?:of|was|=)\s+(\d+\.?\d*)'
    ]
    
    min_age = 100
    max_age = 0
    
    for pattern in age_patterns:
        matches = re.finditer(pattern, abstract_lower)
        for match in matches:
            try:
                if len(match.groups()) >= 2:
                    # 年齢範囲の場合
                    age1 = float(match.group(1))
                    age2 = float(match.group(2))
                    min_age = min(min_age, age1, age2)
                    max_age = max(max_age, age1, age2)
                else:
                    # 平均年齢の場合
                    age = float(match.group(1))
                    min_age = min(min_age, age - 5)  # 平均年齢の前後5年を仮定
                    max_age = max(max_age, age + 5)
            except (IndexError, ValueError):
                continue
    
    # 年齢範囲に基づく判定
    if min_age < 100 and max_age > 0:
        if min_age < 13 and max_age < 18:
            return "小児"
        elif min_age < 18 and max_age < 25:
            return "小児・青年"
        elif min_age >= 18 and max_age < 60:
            return "成人"
        elif min_age >= 40:
            return "成人・高齢者"
        else:
            return "全年齢"
    
    # キーワードに基づく判定
    if any(term in abstract_lower for term in children_terms):
        if any(term in abstract_lower for term in adolescent_terms):
            return "小児・青年"
        return "小児"
    elif any(term in abstract_lower for term in adolescent_terms):
        return "青年"
    elif any(term in abstract_lower for term in adult_terms):
        if any(term in abstract_lower for term in elderly_terms):
            return "成人・高齢者"
        return "成人"
    elif any(term in abstract_lower for term in elderly_terms):
        return "高齢者"
    
    # デフォルト
    return "全年齢"

def extract_risk_description(title, abstract):
    """
    タイトルと抄録からリスク記述を抽出します。
    """
    if not abstract:
        return title
    
    # 抄録から数値と関連する記述を探す
    risk_patterns = [
        r'(\d+\.?\d*)%\s+(?:increase|higher|greater|elevated)\s+risk',
        r'risk\s+(?:increased|higher|greater|elevated)\s+by\s+(\d+\.?\d*)%',
        r'odds\s+ratio\s+(?:of|was|=)\s+(\d+\.?\d*)',
        r'(?:relative|absolute)\s+risk\s+(?:of|was|=)\s+(\d+\.?\d*)',
        r'hazard\s+ratio\s+(?:of|was|=)\s+(\d+\.?\d*)'
    ]
    
    for pattern in risk_patterns:
        matches = re.search(pattern, abstract, re.IGNORECASE)
        if matches:
            try:
                risk_value = float(matches.group(1))
                context_start = max(0, matches.start() - 50)
                context_end = min(len(abstract), matches.end() + 50)
                risk_context = abstract[context_start:context_end].strip()
                return f"{risk_value:.1f}%上昇 ({risk_context}...)"
            except (IndexError, ValueError):
                continue
    
    # リスク表現が見つからない場合は、タイトルを簡易的な記述として返す
    if len(title) > 100:
        return title[:100] + "..."
    return title

def update_papers_csv(new_articles, csv_file='papers.csv'):
    """
    新しい論文データをCSVファイルに追加または更新します。
    """
    try:
        # 既存のCSVを読み込むか、新しいデータフレームを作成
        try:
            existing_df = pd.read_csv(csv_file)
            # DOIの列が存在するか確認
            if 'doi' not in existing_df.columns:
                existing_df['doi'] = "不明"
        except (FileNotFoundError, pd.errors.EmptyDataError):
            # 新しいデータフレームを作成
            existing_df = pd.DataFrame(columns=[
                'issue', 'risk_description', 'doi', 'publication_year', 
                'study_type', 'sample_size', 'confidence_interval', 'age_group',
                'evidence_level', 'authors', 'title'
            ])
        
        # 新しい論文をデータフレームに変換
        new_rows = []
        for article in new_articles:
            # サンプルサイズの整形
            sample_size_str = str(article['sample_size']) if article['sample_size'] else "不明"
            
            # 信頼区間の整形
            ci_str = article['confidence_interval'] if article['confidence_interval'] else "不明"
            
            # 歯列問題の分類
            issue = classify_dental_issue(
                article['title'], 
                article['abstract'], 
                article['keywords'], 
                article['mesh_terms']
            )
            
            # リスク記述の抽出
            risk_description = extract_risk_description(article['title'], article['abstract'])
            
            # エビデンスレベルの取得
            evidence_level = map_study_type_to_evidence_level(article['study_type'])
            
            # 既存データにDOIがある場合は重複を避ける
            if 'doi' in existing_df.columns and article['doi'] in existing_df['doi'].values:
                continue
            
            # 新しい行を追加
            new_rows.append({
                'issue': issue,
                'risk_description': risk_description,
                'doi': article['doi'],
                'publication_year': article['publication_year'],
                'study_type': article['study_type'],
                'sample_size': sample_size_str,
                'confidence_interval': ci_str,
                'age_group': article['age_group'],
                'evidence_level': evidence_level,
                'authors': article['authors'],
                'title': article['title'],
                'url': article['url']
            })
        
        # 新しいデータがある場合のみ処理
        if new_rows:
            new_df = pd.DataFrame(new_rows)
            # 既存のデータと新しいデータを連結
            updated_df = pd.concat([existing_df, new_df], ignore_index=True)
            # CSVに保存
            updated_df.to_csv(csv_file, index=False)
            return updated_df
        
        return existing_df
        
    except Exception as e:
        print(f"CSVファイル更新エラー: {e}")
        return pd.DataFrame()

def render_evidence_level_badge(evidence_level, study_type="", sample_size=""):
    """
    エビデンスレベルを視覚的に表示するHTMLを生成します。
    """
    # エビデンスレベルによる色と説明のマッピング
    level_colors = {
        "1a": {"color": "#4CAF50", "bg": "#E8F5E9", "text": "メタ分析/システマティックレビュー"},
        "1b": {"color": "#8BC34A", "bg": "#F1F8E9", "text": "ランダム化比較試験"},
        "2a": {"color": "#FFC107", "bg": "#FFF8E1", "text": "コホート研究"},
        "2b": {"color": "#FF9800", "bg": "#FFF3E0", "text": "症例対照研究/臨床試験"},
        "3": {"color": "#FF5722", "bg": "#FBE9E7", "text": "横断研究/実験研究"},
        "4": {"color": "#F44336", "bg": "#FFEBEE", "text": "症例報告/症例シリーズ"},
        "5": {"color": "#9E9E9E", "bg": "#F5F5F5", "text": "専門家意見/不明"}
    }
    
    level_info = level_colors.get(evidence_level, level_colors["5"])
    
    # サンプルサイズの表示形式
    sample_display = f"n={sample_size}" if sample_size and sample_size != "不明" else ""
    
    # 研究タイプの表示形式
    study_display = study_type.replace('-', ' ').title() if study_type else ""
    
    # HTMLコード生成
    html = f"""
    <div style="border-left: 4px solid {level_info['color']};
                padding: 8px;
                margin: 5px 0;
                background-color: {level_info['bg']};
                border-radius: 4px;">
        <div style="font-weight: bold; color: {level_info['color']};">
            エビデンスレベル {evidence_level}: {level_info['text']}
        </div>
        <div style="font-size: 0.85em; color: #555;">
            {study_display} {sample_display}
        </div>
    </div>
    """
    
    return html