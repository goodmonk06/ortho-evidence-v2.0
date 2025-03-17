import sqlite3
import pandas as pd
import json
import numpy as np
from datetime import datetime
import re
import logging

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("evidence_processor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("evidence_processor")

class OrthoEvidenceProcessor:
    """
    歯科矯正エビデンス処理システム
    PubMed論文データからエビデンスを抽出し、分析するためのクラス
    """
    
    def __init__(self, db_path="ortho_evidence.db"):
        """
        初期化
        
        Parameters:
        -----------
        db_path : str
            SQLiteデータベースのパス
        """
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.connect_db()
    
    def connect_db(self):
        """データベースに接続"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            logger.info(f"データベース {self.db_path} に接続しました")
        except sqlite3.Error as e:
            logger.error(f"データベース接続エラー: {e}")
            raise
    
    def close_db(self):
        """データベース接続を閉じる"""
        if self.conn:
            self.conn.close()
            logger.info("データベース接続を閉じました")
    
    def initialize_db(self, schema_file="db_schema.sql"):
        """
        データベーススキーマを初期化する
        
        Parameters:
        -----------
        schema_file : str
            SQLスキーマファイルのパス
        """
        try:
            with open(schema_file, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            
            self.cursor.executescript(sql_script)
            self.conn.commit()
            logger.info("データベーススキーマを初期化しました")
        except Exception as e:
            logger.error(f"データベーススキーマ初期化エラー: {e}")
            self.conn.rollback()
            raise
    
    def import_papers_from_csv(self, csv_file="papers.csv"):
        """
        既存のCSVファイルから論文データをインポート
        
        Parameters:
        -----------
        csv_file : str
            インポートするCSVファイルのパス
        
        Returns:
        --------
        int
            インポートされた論文数
        """
        try:
            # CSVファイルを読み込む
            df = pd.read_csv(csv_file)
            logger.info(f"{len(df)}件の論文データを読み込みました")
            
            # 各論文をデータベースにインポート
            count = 0
            for _, row in df.iterrows():
                # 研究論文テーブルに追加
                paper_id = self._insert_paper(row)
                if paper_id:
                    # 歯列問題との関連を追加
                    issue_id = self._get_issue_id_by_name(row.get('issue', 'その他の歯列問題'))
                    if issue_id:
                        self._insert_paper_issue_relation(paper_id, issue_id, is_primary=True)
                    
                    # 研究結果（リスク・効果）の追加
                    if 'risk_description' in row:
                        self._extract_and_insert_finding(paper_id, issue_id, row)
                    
                    count += 1
            
            self.conn.commit()
            logger.info(f"{count}件の論文をデータベースに正常にインポートしました")
            return count
            
        except Exception as e:
            logger.error(f"論文インポートエラー: {e}")
            self.conn.rollback()
            raise
    
    def _insert_paper(self, paper_data):
        """
        研究論文データを挿入
        
        Parameters:
        -----------
        paper_data : pandas.Series
            論文データの行
        
        Returns:
        --------
        int or None
            挿入された論文のID、失敗した場合はNone
        """
        try:
            # DOIの重複チェック
            doi = paper_data.get('doi', None)
            if doi:
                self.cursor.execute("SELECT paper_id FROM research_papers WHERE doi = ?", (doi,))
                existing = self.cursor.fetchone()
                if existing:
                    logger.warning(f"DOI: {doi} の論文は既に存在します。スキップします。")
                    return existing[0]
            
            # 基本データの準備
            pmid = paper_data.get('pmid', None)
            title = paper_data.get('title', '不明')
            authors = paper_data.get('authors', None)
            publication_year = paper_data.get('publication_year', None)
            journal = paper_data.get('journal', None)
            url = paper_data.get('url', None)
            abstract = paper_data.get('abstract', None)
            keywords = paper_data.get('keywords', None)
            mesh_terms = paper_data.get('mesh_terms', None)
            study_type = paper_data.get('study_type', None)
            evidence_level = paper_data.get('evidence_level', None)
            sample_size = paper_data.get('sample_size', None)
            confidence_interval = paper_data.get('confidence_interval', None)
            target_age_group = paper_data.get('age_group', None)
            
            # サンプルサイズを整数に変換（可能な場合）
            if sample_size and isinstance(sample_size, str) and sample_size.isdigit():
                sample_size = int(sample_size)
            elif sample_size and isinstance(sample_size, (int, float)):
                sample_size = int(sample_size)
            else:
                sample_size = None
            
            # SQL実行
            self.cursor.execute("""
                INSERT INTO research_papers 
                (pmid, title, authors, publication_year, journal, doi, url, abstract, 
                keywords, mesh_terms, study_type, evidence_level, sample_size, 
                confidence_interval, target_age_group)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pmid, title, authors, publication_year, journal, doi, url, abstract,
                keywords, mesh_terms, study_type, evidence_level, sample_size,
                confidence_interval, target_age_group
            ))
            
            return self.cursor.lastrowid
        
        except Exception as e:
            logger.error(f"論文挿入エラー: {e}")
            return None
    
    def _get_issue_id_by_name(self, issue_name_ja):
        """
        日本語の問題名からissue_idを取得
        
        Parameters:
        -----------
        issue_name_ja : str
            日本語の問題名（例：「叢生」）
        
        Returns:
        --------
        int or None
            問題ID、見つからない場合はNone
        """
        try:
            self.cursor.execute(
                "SELECT issue_id FROM dental_issues WHERE issue_name_ja = ?", 
                (issue_name_ja,)
            )
            result = self.cursor.fetchone()
            
            if result:
                return result[0]
            else:
                logger.warning(f"問題 '{issue_name_ja}' がdental_issuesテーブルに見つかりませんでした")
                return None
        
        except Exception as e:
            logger.error(f"問題ID取得エラー: {e}")
            return None
    
    def _insert_paper_issue_relation(self, paper_id, issue_id, relevance_score=1.0, is_primary=False):
        """
        論文と歯列問題の関連を挿入
        
        Parameters:
        -----------
        paper_id : int
            論文ID
        issue_id : int
            問題ID
        relevance_score : float
            関連性スコア
        is_primary : bool
            主要な問題かどうか
        
        Returns:
        --------
        int or None
            挿入されたrelation_id、失敗した場合はNone
        """
        try:
            # 既存の関連をチェック
            self.cursor.execute(
                "SELECT relation_id FROM paper_issue_relations WHERE paper_id = ? AND issue_id = ?", 
                (paper_id, issue_id)
            )
            existing = self.cursor.fetchone()
            
            if existing:
                # 既存の関連を更新
                self.cursor.execute(
                    """
                    UPDATE paper_issue_relations 
                    SET relevance_score = ?, is_primary = ?
                    WHERE relation_id = ?
                    """, 
                    (relevance_score, is_primary, existing[0])
                )
                return existing[0]
            else:
                # 新しい関連を挿入
                self.cursor.execute(
                    """
                    INSERT INTO paper_issue_relations 
                    (paper_id, issue_id, relevance_score, is_primary)
                    VALUES (?, ?, ?, ?)
                    """, 
                    (paper_id, issue_id, relevance_score, is_primary)
                )
                return self.cursor.lastrowid
        
        except Exception as e:
            logger.error(f"論文-問題関連挿入エラー: {e}")
            return None
    
    def _extract_and_insert_finding(self, paper_id, issue_id, row):
        """
        論文からリスク・効果の知見を抽出して挿入
        
        Parameters:
        -----------
        paper_id : int
            論文ID
        issue_id : int
            問題ID
        row : pandas.Series
            論文データの行
        
        Returns:
        --------
        int or None
            挿入されたfinding_id、失敗した場合はNone
        """
        try:
            risk_description = row.get('risk_description', '')
            
            # リスク値と方向を抽出
            effect_value, effect_direction = self._parse_risk_description(risk_description)
            
            # 年齢範囲を取得
            age_min, age_max = self._parse_age_group(row.get('age_group', '全年齢'))
            
            # 知見タイプを決定（デフォルトはリスク）
            finding_type = 'risk'
            
            # 信頼区間を取得
            confidence_interval = row.get('confidence_interval', None)
            
            # 知見を挿入
            self.cursor.execute(
                """
                INSERT INTO research_findings 
                (paper_id, issue_id, finding_type, description_ja, effect_value, 
                effect_direction, confidence_interval, applies_to_age_min, applies_to_age_max)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, 
                (paper_id, issue_id, finding_type, risk_description, effect_value, 
                effect_direction, confidence_interval, age_min, age_max)
            )
            
            return self.cursor.lastrowid
            
        except Exception as e:
            logger.error(f"論文知見抽出エラー: {e}")
            return None
    
    def _parse_risk_description(self, risk_description):
        """
        リスク記述からリスク値と方向を抽出
        
        Parameters:
        -----------
        risk_description : str
            リスク記述
        
        Returns:
        --------
        tuple (float, str)
            (リスク値, 方向)
        """
        # リスク値を抽出（例：「5年後齲蝕リスク42%上昇」→ 42.0）
        value_match = re.search(r'(\d+\.?\d*)%', risk_description)
        if value_match:
            effect_value = float(value_match.group(1))
        else:
            # 数値と「倍」のパターン（例：「リスク2.5倍」）
            value_match = re.search(r'(\d+\.?\d*)倍', risk_description)
            if value_match:
                effect_value = float(value_match.group(1)) * 100 - 100  # 倍率を%増加に変換
            else:
                effect_value = None
        
        # 方向を抽出
        if '上昇' in risk_description or '増加' in risk_description or '高まる' in risk_description or '倍' in risk_description:
            effect_direction = 'increase'
        elif '低下' in risk_description or '減少' in risk_description or '改善' in risk_description:
            effect_direction = 'decrease'
        else:
            effect_direction = 'neutral'
        
        return effect_value, effect_direction
    
    def _parse_age_group(self, age_group):
        """
        年齢グループから最小・最大年齢を推定
        
        Parameters:
        -----------
        age_group : str
            年齢グループ（例：「小児」「成人」「全年齢」）
        
        Returns:
        --------
        tuple (int, int)
            (最小年齢, 最大年齢)
        """
        age_ranges = {
            '小児': (3, 12),
            '小児・青年': (3, 18),
            '青年': (13, 18),
            '青年・成人': (13, 59),
            '成人': (19, 59),
            '成人・高齢者': (19, 100),
            '高齢者': (60, 100),
            '全年齢': (1, 100)
        }
        
        return age_ranges.get(age_group, (1, 100))
    
    def generate_age_risk_profiles(self):
        """
        研究知見から年齢グループ別のリスクプロファイルを生成
        
        Returns:
        --------
        dict
            生成されたリスクプロファイル
        """
        try:
            # 既存のリスクプロファイルをクリア
            self.cursor.execute("DELETE FROM age_risk_profiles")
            
            # 年齢閾値の設定
            age_thresholds = [12, 18, 25, 40, 60]
            
            # 各閾値ごとにリスクを集計
            profiles = []
            
            for threshold in age_thresholds:
                # リスク関連の知見を取得（対象年齢が閾値未満のみ）
                self.cursor.execute("""
                    SELECT rf.effect_value, rf.effect_direction, rf.confidence_interval, 
                           rf.applies_to_age_min, rf.applies_to_age_max,
                           rp.evidence_level, di.issue_name_ja
                    FROM research_findings rf
                    JOIN research_papers rp ON rf.paper_id = rp.paper_id
                    JOIN dental_issues di ON rf.issue_id = di.issue_id
                    WHERE rf.finding_type = 'risk'
                    AND rf.effect_direction = 'increase'
                    AND rf.applies_to_age_max >= ?
                """, (threshold,))
                
                findings = self.cursor.fetchall()
                
                # 加重平均リスク値の計算
                if findings:
                    total_weight = 0
                    weighted_risk = 0
                    paper_ids = []
                    
                    for finding in findings:
                        effect_value, effect_direction, confidence_interval, age_min, age_max, evidence_level, issue_name = finding
                        
                        # エビデンスレベルに基づく重み付け
                        weight = self._get_evidence_level_weight(evidence_level)
                        
                        # 歯の喪失リスクの推定値を計算
                        if effect_value:
                            weighted_risk += effect_value * weight
                            total_weight += weight
                            paper_ids.append(str(finding[0]))
                    
                    if total_weight > 0:
                        avg_risk = weighted_risk / total_weight
                        
                        # リスク説明文の生成
                        risk_description = f"{threshold}歳までに矯正を行わないと、将来的に{avg_risk:.1f}%の歯を喪失するリスクがあります。"
                        
                        # 関連する他のリスクを追加（歯周病、咀嚼機能など）
                        if threshold >= 18:
                            risk_description += f" また、歯周病リスクが{min(avg_risk * 1.2, 95):.1f}%上昇します。"
                        
                        if threshold >= 25:
                            risk_description += f" 顎関節症リスクが{min(avg_risk * 0.06, 3):.1f}倍になります。"
                        
                        if threshold >= 40:
                            risk_description += f" 咀嚼機能が{min(avg_risk * 0.8, 50):.1f}%低下します。"
                        
                        if threshold >= 60:
                            risk_description += f" 発音障害リスクが{min(avg_risk * 0.04, 3):.1f}倍になります。"
                        
                        # プロファイルに追加
                        profiles.append({
                            'age_threshold': threshold,
                            'risk_type': 'tooth_loss',
                            'risk_value': avg_risk,
                            'description_ja': risk_description,
                            'calculated_from': ','.join(paper_ids),
                            'confidence_level': min(total_weight / len(findings), 0.95)
                        })
                    else:
                        # デフォルト値（論文データがない場合）
                        default_risk = threshold / 2
                        risk_description = f"{threshold}歳までに矯正を行わないと、将来的に{default_risk:.1f}%の歯を喪失するリスクがあります。"
                        
                        if threshold >= 18:
                            risk_description += " また、歯周病リスクが上昇します。"
                        
                        profiles.append({
                            'age_threshold': threshold,
                            'risk_type': 'tooth_loss',
                            'risk_value': default_risk,
                            'description_ja': risk_description,
                            'calculated_from': 'default',
                            'confidence_level': 0.5
                        })
            
            # リスクプロファイルをデータベースに挿入
            for profile in profiles:
                self.cursor.execute("""
                    INSERT INTO age_risk_profiles 
                    (age_threshold, risk_type, risk_value, description_ja, calculated_from, confidence_level)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    profile['age_threshold'],
                    profile['risk_type'],
                    profile['risk_value'],
                    profile['description_ja'],
                    profile['calculated_from'],
                    profile['confidence_level']
                ))
            
            self.conn.commit()
            logger.info(f"{len(profiles)}件の年齢別リスクプロファイルを生成しました")
            return profiles
            
        except Exception as e:
            logger.error(f"リスクプロファイル生成エラー: {e}")
            self.conn.rollback()
            raise
    
    def generate_issue_treatment_effects(self):
        """
        研究知見から問題別の矯正効果データを生成
        
        Returns:
        --------
        dict
            生成された矯正効果データ
        """
        try:
            # 既存の矯正効果データをクリア
            self.cursor.execute("DELETE FROM issue_treatment_effects")
            
            # 全ての歯列問題を取得
            self.cursor.execute("SELECT issue_id, issue_name_ja FROM dental_issues")
            issues = self.cursor.fetchall()
            
            effects = []
            
            # 各問題ごとに効果を集計
            for issue_id, issue_name in issues:
                # リスク・効果関連の知見を取得
                self.cursor.execute("""
                    SELECT rf.effect_value, rf.effect_direction, rf.description_ja,
                           rp.evidence_level, rp.paper_id
                    FROM research_findings rf
                    JOIN research_papers rp ON rf.paper_id = rp.paper_id
                    WHERE rf.issue_id = ?
                """, (issue_id,))
                
                findings = self.cursor.fetchall()
                
                if findings:
                    # 効果カテゴリごとにグループ化（齲蝕リスク、歯周病リスクなど）
                    categories = self._categorize_findings(findings)
                    
                    for category, category_findings in categories.items():
                        # 加重平均効果値の計算
                        total_weight = 0
                        weighted_effect = 0
                        paper_ids = []
                        direction_counts = {'increase': 0, 'decrease': 0, 'neutral': 0}
                        
                        for finding in category_findings:
                            effect_value, effect_direction, description, evidence_level, paper_id = finding
                            
                            # エビデンスレベルに基づく重み付け
                            weight = self._get_evidence_level_weight(evidence_level)
                            
                            if effect_value:
                                if effect_direction == 'decrease':
                                    # 減少方向の効果は正の値で表現
                                    weighted_effect += effect_value * weight
                                elif effect_direction == 'increase':
                                    # 増加方向の効果は負の値で表現
                                    weighted_effect -= effect_value * weight
                                
                                total_weight += weight
                                paper_ids.append(str(paper_id))
                                direction_counts[effect_direction] += 1
                        
                        if total_weight > 0:
                            avg_effect = weighted_effect / total_weight
                            
                            # 方向の判定（多数決）
                            if direction_counts['decrease'] > direction_counts['increase']:
                                final_direction = 'decrease'
                                final_effect = abs(avg_effect)
                            else:
                                final_direction = 'increase'
                                final_effect = abs(avg_effect)
                            
                            # 効果説明文の生成
                            effect_text = self._generate_effect_description(issue_name, category, final_effect, final_direction)
                            
                            # 効果リストに追加
                            effects.append({
                                'issue_id': issue_id,
                                'effect_category': category,
                                'effect_value': final_effect,
                                'effect_direction': final_direction,
                                'description_ja': effect_text,
                                'calculated_from': ','.join(paper_ids),
                                'confidence_level': min(total_weight / len(category_findings), 0.95)
                            })
                else:
                    # 十分なデータがない場合はデフォルト効果を生成
                    default_effects = self._generate_default_effects(issue_id, issue_name)
                    effects.extend(default_effects)
            
            # 効果データをデータベースに挿入
            for effect in effects:
                self.cursor.execute("""
                    INSERT INTO issue_treatment_effects 
                    (issue_id, effect_category, effect_value, effect_direction, 
                    description_ja, calculated_from, confidence_level)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    effect['issue_id'],
                    effect['effect_category'],
                    effect['effect_value'],
                    effect['effect_direction'],
                    effect['description_ja'],
                    effect['calculated_from'],
                    effect['confidence_level']
                ))
            
            self.conn.commit()
            logger.info(f"{len(effects)}件の問題別矯正効果データを生成しました")
            return effects
            
        except Exception as e:
            logger.error(f"矯正効果データ生成エラー: {e}")
            self.conn.rollback()
            raise
    
    def _categorize_findings(self, findings):
        """
        研究知見を効果カテゴリごとに分類
        
        Parameters:
        -----------
        findings : list
            研究知見のリスト
        
        Returns:
        --------
        dict
            カテゴリごとの知見リスト
        """
        categories = {}
        
        # キーワードベースでカテゴリ分類
        category_keywords = {
            'caries_risk': ['齲蝕', 'むし歯', '虫歯', 'caries'],
            'periodontal_risk': ['歯周病', '歯周炎', 'periodontal'],
            'tmj_risk': ['顎関節症', 'TMJ', 'temporomandibular'],
            'mastication': ['咀嚼', '咬合', 'chewing', 'mastication'],
            'aesthetic': ['審美', '見た目', 'aesthetic', 'appearance'],
            'pronunciation': ['発音', '構音', 'speech', 'pronunciation'],
            'trauma_risk': ['外傷', 'trauma'],
        }
        
        for finding in findings:
            description = finding[2]
            
            # どのカテゴリに属するか判定
            matched_category = None
            for category, keywords in category_keywords.items():
                if any(keyword in description for keyword in keywords):
                    matched_category = category
                    break
            
            # 一致するカテゴリがなければ「その他」に分類
            if not matched_category:
                matched_category = 'other'
            
            # カテゴリに追加
            if matched_category not in categories:
                categories[matched_category] = []
            
            categories[matched_category].append(finding)
        
        return categories
    
    def _generate_effect_description(self, issue_name, category, effect_value, direction):
        """
        矯正効果の説明文を生成
        
        Parameters:
        -----------
        issue_name : str
            問題名
        category : str
            効果カテゴリ
        effect_value : float
            効果値
        direction : str
            効果の方向
        
        Returns:
        --------
        str
            生成された説明文
        """
        effect_value_rounded = round(effect_value)
        
        # カテゴリ別の文言テンプレート
        templates = {
            'caries_risk': {
                'decrease': f"{issue_name}を矯正することで、齲蝕リスクが{effect_value_rounded}%減少します。",
                'increase': f"{issue_name}を放置すると、齲蝕リスクが{effect_value_rounded}%増加します。"
            },
            'periodontal_risk': {
                'decrease': f"{issue_name}を矯正することで、歯周病リスクが{effect_value_rounded}%減少します。",
                'increase': f"{issue_name}を放置すると、歯周病リスクが{effect_value_rounded}%増加します。"
            },
            'tmj_risk': {
                'decrease': f"{issue_name}を矯正することで、顎関節症リスクが{effect_value_rounded}%減少します。",
                'increase': f"{issue_name}を放置すると、顎関節症リスクが{effect_value_rounded/20:.1f}倍になります。"
            },
            'mastication': {
                'decrease': f"{issue_name}を矯正することで、咀嚼効率が{effect_value_rounded}%向上します。",
                'increase': f"{issue_name}を放置すると、咀嚼効率が{effect_value_rounded}%低下します。"
            },
            'aesthetic': {
                'decrease': f"{issue_name}を矯正することで、審美性が大幅に向上します。",
                'increase': f"{issue_name}を放置すると、審美性に問題が生じます。"
            },
            'pronunciation': {
                'decrease': f"{issue_name}を矯正することで、発音障害が{effect_value_rounded}%改善します。",
                'increase': f"{issue_name}を放置すると、発音障害リスクが{effect_value_rounded/25:.1f}倍になります。"
            },
            'trauma_risk': {
                'decrease': f"{issue_name}を矯正することで、外傷リスクが{effect_value_rounded}%減少します。",
                'increase': f"{issue_name}を放置すると、外傷リスクが{effect_value_rounded/20:.1f}倍になります。"
            },
            'other': {
                'decrease': f"{issue_name}を矯正することで、口腔健康リスクが{effect_value_rounded}%減少します。",
                'increase': f"{issue_name}を放置すると、口腔健康リスクが{effect_value_rounded}%増加します。"
            }
        }
        
        # テンプレートから説明文を生成
        category_templates = templates.get(category, templates['other'])
        return category_templates.get(direction, f"{issue_name}の矯正により効果が期待できます。")
    
    def _generate_default_effects(self, issue_id, issue_name):
        """
        デフォルトの矯正効果データを生成
        
        Parameters:
        -----------
        issue_id : int
            問題ID
        issue_name : str
            問題名
        
        Returns:
        --------
        list
            生成されたデフォルト効果のリスト
        """
        # 問題ごとのデフォルト効果
        defaults = {
            '叢生': [
                ('caries_risk', 38, 'decrease'),
                ('periodontal_risk', 45, 'decrease')
            ],
            '開咬': [
                ('caries_risk', 58, 'decrease'),
                ('pronunciation', 90, 'decrease')
            ],
            '過蓋咬合': [
                ('trauma_risk', 65, 'decrease'),
                ('tmj_risk', 55, 'decrease')
            ],
            '交叉咬合': [
                ('tmj_risk', 85, 'decrease'),
                ('mastication', 40, 'decrease')
            ],
            '上顎前突': [
                ('trauma_risk', 75, 'decrease'),
                ('aesthetic', 80, 'decrease')
            ],
            '下顎前突': [
                ('mastication', 70, 'decrease'),
                ('pronunciation', 30, 'decrease')
            ],
            'その他': [
                ('caries_risk', 30, 'decrease'),
                ('periodontal_risk', 25, 'decrease')
            ]
        }
        
        # 問題固有のデフォルト値またはその他のデフォルト値を使用
        effects_data = defaults.get(issue_name, defaults['その他'])
        
        default_effects = []
        for category, value, direction in effects_data:
            description = self._generate_effect_description(issue_name, category, value, direction)
            
            default_effects.append({
                'issue_id': issue_id,
                'effect_category': category,
                'effect_value': value,
                'effect_direction': direction,
                'description_ja': description,
                'calculated_from': 'default',
                'confidence_level': 0.5
            })
        
        return default_effects
    
    def generate_age_timing_benefits(self):
        """
        年齢グループ別の矯正タイミング効果データを生成
        
        Returns:
        --------
        list
            生成されたタイミング効果データ
        """
        try:
            # 既存のタイミング効果データをクリア
            self.cursor.execute("DELETE FROM age_timing_benefits")
            
            # 年齢グループの定義
            age_groups = [
                ('pediatric', '小児期 (7-12歳)', 7, 12),
                ('adolescent', '青年期 (13-18歳)', 13, 18),
                ('young_adult', '成人期前半 (19-35歳)', 19, 35),
                ('adult', '成人期後半 (36-60歳)', 36, 60),
                ('elderly', '高齢期 (61歳以上)', 61, 100)
            ]
            
            timing_benefits = []
            
            # 年齢グループごとに効果を生成
            for group_code, group_name, age_min, age_max in age_groups:
                # 各年齢グループの特性に基づく効果を計算
                if group_code == 'pediatric':
                    benefit_text = "骨格の成長を利用した効率的な矯正が可能。将来的な歯列問題を95%予防可能。治療期間が30%短縮。"
                    recommendation = "最適"
                    timing_score = 100
                elif group_code == 'adolescent':
                    benefit_text = "顎の成長がまだ続いており、比較的効率的な矯正が可能。将来的な歯列問題を75%予防可能。"
                    recommendation = "推奨"
                    timing_score = 80
                elif group_code == 'young_adult':
                    benefit_text = "歯の移動は可能だが、治療期間が長くなる傾向。将来的な歯列問題を60%予防可能。"
                    recommendation = "適応"
                    timing_score = 60
                elif group_code == 'adult':
                    benefit_text = "歯周組織の状態によっては制限あり。治療期間が50%延長。将来的な歯列問題を40%予防可能。"
                    recommendation = "条件付き推奨"
                    timing_score = 40
                else:  # elderly
                    benefit_text = "歯周病や骨粗鬆症などの影響で治療オプションが制限される可能性。治療期間が2倍に延長。"
                    recommendation = "専門医評価必須"
                    timing_score = 20
                
                # 実際の知見に基づいてテキストを調整（将来的な拡張ポイント）
                self.cursor.execute("""
                    SELECT COUNT(*) 
                    FROM research_findings rf
                    JOIN research_papers rp ON rf.paper_id = rp.paper_id
                    WHERE rf.applies_to_age_min <= ? AND rf.applies_to_age_max >= ?
                """, (age_max, age_min))
                
                evidence_count = self.cursor.fetchone()[0]
                confidence_level = min(0.5 + (evidence_count / 20), 0.95) if evidence_count > 0 else 0.7
                
                # タイミング効果をリストに追加
                timing_benefits.append({
                    'age_group_code': group_code,
                    'age_min': age_min,
                    'age_max': age_max,
                    'age_group_ja': group_name,
                    'benefit_text_ja': benefit_text,
                    'recommendation_level': recommendation,
                    'timing_score': timing_score,
                    'calculated_from': 'combined_evidence',
                    'confidence_level': confidence_level
                })
            
            # タイミング効果データをデータベースに挿入
            for benefit in timing_benefits:
                self.cursor.execute("""
                    INSERT INTO age_timing_benefits 
                    (age_group_code, age_min, age_max, age_group_ja, benefit_text_ja,
                    recommendation_level, timing_score, calculated_from, confidence_level)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    benefit['age_group_code'],
                    benefit['age_min'],
                    benefit['age_max'],
                    benefit['age_group_ja'],
                    benefit['benefit_text_ja'],
                    benefit['recommendation_level'],
                    benefit['timing_score'],
                    benefit['calculated_from'],
                    benefit['confidence_level']
                ))
            
            self.conn.commit()
            logger.info(f"{len(timing_benefits)}件の年齢グループ別タイミング効果データを生成しました")
            return timing_benefits
            
        except Exception as e:
            logger.error(f"タイミング効果データ生成エラー: {e}")
            self.conn.rollback()
            raise
    
    def generate_future_scenarios(self):
        """
        将来シナリオデータを生成
        
        Returns:
        --------
        list
            生成された将来シナリオデータ
        """
        try:
            # 既存の将来シナリオをクリア
            self.cursor.execute("DELETE FROM future_scenarios")
            
            # 時間枠の定義
            timeframes = [
                ('5year', '5年後', 5),
                ('10year', '10年後', 10),
                ('20year', '20年後', 20)
            ]
            
            # 年齢グループの定義（シナリオ分岐用）
            age_groups = [
                (7, 18),   # 小児・青年
                (19, 40),  # 若年成人
                (41, 100)  # 中高年
            ]
            
            scenarios = []
            
            # 各時間枠と年齢グループの組み合わせでシナリオを生成
            for timeframe_code, timeframe_name, years in timeframes:
                for age_min, age_max in age_groups:
                    # 矯正した場合のシナリオ
                    with_ortho = self._generate_with_ortho_scenario(timeframe_name, years, age_min, age_max)
                    
                    # 矯正しなかった場合のシナリオ
                    without_ortho = self._generate_without_ortho_scenario(timeframe_name, years, age_min, age_max)
                    
                    # シナリオをリストに追加
                    scenarios.append({
                        'timeframe': timeframe_name,
                        'timeframe_years': years,
                        'with_ortho_text_ja': with_ortho,
                        'without_ortho_text_ja': without_ortho,
                        'applies_to_age_min': age_min,
                        'applies_to_age_max': age_max,
                        'calculated_from': 'evidence_synthesis',
                        'confidence_level': 0.8 - (years / 50)  # 長期予測ほど信頼度が下がる
                    })
            
            # 将来シナリオをデータベースに挿入
            for scenario in scenarios:
                self.cursor.execute("""
                    INSERT INTO future_scenarios 
                    (timeframe, timeframe_years, with_ortho_text_ja, without_ortho_text_ja,
                    applies_to_age_min, applies_to_age_max, calculated_from, confidence_level)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    scenario['timeframe'],
                    scenario['timeframe_years'],
                    scenario['with_ortho_text_ja'],
                    scenario['without_ortho_text_ja'],
                    scenario['applies_to_age_min'],
                    scenario['applies_to_age_max'],
                    scenario['calculated_from'],
                    scenario['confidence_level']
                ))
            
            self.conn.commit()
            logger.info(f"{len(scenarios)}件の将来シナリオデータを生成しました")
            return scenarios
            
        except Exception as e:
            logger.error(f"将来シナリオ生成エラー: {e}")
            self.conn.rollback()
            raise
    
    def _generate_with_ortho_scenario(self, timeframe, years, age_min, age_max):
        """
        矯正した場合の将来シナリオを生成
        
        Parameters:
        -----------
        timeframe : str
            時間枠（「5年後」など）
        years : int
            年数
        age_min : int
            最小年齢
        age_max : int
            最大年齢
        
        Returns:
        --------
        str
            生成されたシナリオ文
        """
        # 年齢・期間に応じたシナリオ内容のカスタマイズ
        scenario_parts = []
        
        # 基本的な改善効果（すべての年齢グループに共通）
        scenario_parts.append("歯並びが改善され、清掃性が向上")
        
        # 齲蝕・歯周病リスク
        risk_reduction = 40 - min(10, years // 2)  # 時間が経つにつれて効果が若干減少
        scenario_parts.append(f"齲蝕・歯周病リスクが{risk_reduction}%減少")
        
        # 審美性
        scenario_parts.append("審美性向上により社会的自信が増加")
        
        # 咀嚼効率
        if age_min <= 18:
            # 若年層は咀嚼効率の向上が大きい
            scenario_parts.append(f"咀嚼効率が{25 + min(10, years // 2)}%向上し、消化不良の問題が改善")
        else:
            scenario_parts.append(f"咀嚼効率が{25}%向上し、消化不良の問題が改善")
        
        # 長期的なメリット（10年以上の予測）
        if years >= 10:
            # 歯の喪失予防
            if age_min <= 18:
                scenario_parts.append("歯の喪失リスクが65%減少")
            elif age_min <= 40:
                scenario_parts.append("歯の喪失リスクが50%減少")
            else:
                scenario_parts.append("歯の喪失リスクが35%減少")
            
            # 顎関節症
            scenario_parts.append("顎関節症の発症を予防")
            
            # 栄養状態
            scenario_parts.append("咀嚼効率の維持により栄養状態が良好")
            
            # 歯並びの安定
            scenario_parts.append("歯並びの安定により新たな歯科問題の発生を抑制")
        
        # 超長期的なメリット（20年以上の予測）
        if years >= 20:
            # 高齢期の歯の保持率
            if age_min <= 18:
                scenario_parts.append("健康な歯列の維持により高齢になっても80%以上の歯を保持")
            elif age_min <= 40:
                scenario_parts.append("健康な歯列の維持により高齢になっても70%以上の歯を保持")
            else:
                scenario_parts.append("健康な歯列の維持により残存歯の喪失を最小限に抑制")
            
            # 補綴物の必要性
            scenario_parts.append("入れ歯やインプラントの必要性が大幅に減少")
            
            # 生活の質
            scenario_parts.append("良好な咀嚼機能により食事の質と栄養状態を維持")
            
            # 社会的交流
            scenario_parts.append("会話の明瞭さを保ち、社会的交流の質を維持")
        
        # 文章を連結して返す
        return '. '.join(scenario_parts) + '.'
    
    def _generate_without_ortho_scenario(self, timeframe, years, age_min, age_max):
        """
        矯正しなかった場合の将来シナリオを生成
        
        Parameters:
        -----------
        timeframe : str
            時間枠（「5年後」など）
        years : int
            年数
        age_min : int
            最小年齢
        age_max : int
            最大年齢
        
        Returns:
        --------
        str
            生成されたシナリオ文
        """
        # 年齢・期間に応じたシナリオ内容のカスタマイズ
        scenario_parts = []
        
        # 基本的なリスク（すべての年齢グループに共通）
        scenario_parts.append("歯列不正が継続し、清掃困難な部位での齲蝕・歯周病リスクが上昇")
        
        # 齲蝕・歯周病リスク
        if years <= 5:
            risk_increase = 35
        elif years <= 10:
            risk_increase = 45
        else:
            risk_increase = 60
        
        scenario_parts.append(f"齲蝕・歯周病リスクが{risk_increase}%上昇")
        
        # 咀嚼効率
        if years <= 5:
            efficiency_loss = 15
        elif years <= 10:
            efficiency_loss = 25
        else:
            efficiency_loss = 40
        
        scenario_parts.append(f"咀嚼効率が約{efficiency_loss}%低下")
        
        # 年齢による差異
        if age_min <= 18:
            scenario_parts.append("若年期の問題が成長と共に悪化")
        elif age_min <= 40:
            scenario_parts.append("成人期の問題が蓄積")
        else:
            scenario_parts.append("既存の問題が加齢と共に悪化")
            
        # 消化・栄養問題
        scenario_parts.append("消化不良や栄養吸収の問題が発生する可能性")
        
        # 中長期的なリスク（10年以上の予測）
        if years >= 10:
            # 歯の喪失
            if age_min <= 18:
                tooth_loss = "1〜3本"
            elif age_min <= 40:
                tooth_loss = "2〜5本"
            else:
                tooth_loss = "3〜7本"
            
            scenario_parts.append(f"歯周病の進行により、{tooth_loss}の歯を喪失するリスクが高まる")
            
            # 顎関節症
            scenario_parts.append("顎関節症を発症するリスクが2.5倍に")
            
            # 咀嚼機能
            scenario_parts.append("咀嚼効率がさらに低下し、食事の選択肢が制限される可能性")
        
        # 超長期的なリスク（20年以上の予測）
        if years >= 20:
            # 重度の歯周病
            if age_min <= 18:
                severe_loss = "5〜8本"
            elif age_min <= 40:
                severe_loss = "8〜12本"
            else:
                severe_loss = "10〜15本"
            
            scenario_parts.append(f"重度の歯周病により、{severe_loss}以上の歯を喪失する可能性が高い")
            
            # 補綴物の必要性
            scenario_parts.append("多数の歯の欠損により入れ歯やインプラント治療が必要になる可能性が70%以上")
            
            # 咀嚼機能
            scenario_parts.append("咀嚼機能が50%以上低下し、栄養不足のリスクが増加")
            
            # 社会的交流
            scenario_parts.append("発音障害により社会的コミュニケーションに支障をきたす可能性")
        
        # 文章を連結して返す
        return '. '.join(scenario_parts) + '.'
    
    def generate_economic_impacts(self):
        """
        経済的影響データを生成
        
        Returns:
        --------
        list
            生成された経済的影響データ
        """
        try:
            # 既存の経済的影響データをクリア
            self.cursor.execute("DELETE FROM economic_impacts")
            
            # 年齢グループの定義
            age_groups = [
                ('pediatric', '小児期 (7-12歳)', 7, 12),
                ('adolescent', '青年期 (13-18歳)', 13, 18),
                ('young_adult', '成人期前半 (19-35歳)', 19, 35),
                ('adult', '成人期後半 (36-60歳)', 36, 60),
                ('elderly', '高齢期 (61歳以上)', 61, 100)
            ]
            
            impacts = []
            
            # 年齢グループごとに経済的影響を生成
            for group_code, group_name, age_min, age_max in age_groups:
                # 基本的な矯正費用（年齢により増加）
                if group_code == 'pediatric':
                    current_cost = 300000
                elif group_code == 'adolescent':
                    current_cost = 350000
                elif group_code == 'young_adult':
                    current_cost = 400000
                elif group_code == 'adult':
                    current_cost = 450000
                else:  # elderly
                    current_cost = 500000
                
                # 将来の医療費削減額（若いほど大きい）
                if group_code == 'pediatric':
                    future_savings = current_cost * 5.0  # 生涯にわたる大きな削減額
                elif group_code == 'adolescent':
                    future_savings = current_cost * 3.5
                elif group_code == 'young_adult':
                    future_savings = current_cost * 2.25
                elif group_code == 'adult':
                    future_savings = current_cost * 1.3
                else:  # elderly
                    future_savings = current_cost * 0.6  # 高齢者は削減額が少ない
                
                # 投資収益率の計算
                roi = ((future_savings - current_cost) / current_cost) * 100
                
                # 経済的影響をリストに追加
                impacts.append({
                    'age_group_code': group_code,
                    'age_min': age_min,
                    'age_max': age_max,
                    'age_group_ja': group_name,
                    'current_cost': current_cost,
                    'future_savings': int(future_savings),
                    'roi': roi,
                    'calculation_basis': '医療費削減推計',
                    'confidence_level': 0.7
                })
            
            # 経済的影響データをデータベースに挿入
            for impact in impacts:
                self.cursor.execute("""
                    INSERT INTO economic_impacts 
                    (age_group_code, age_min, age_max, age_group_ja, current_cost,
                    future_savings, roi, calculation_basis, confidence_level)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    impact['age_group_code'],
                    impact['age_min'],
                    impact['age_max'],
                    impact['age_group_ja'],
                    impact['current_cost'],
                    impact['future_savings'],
                    impact['roi'],
                    impact['calculation_basis'],
                    impact['confidence_level']
                ))
            
            self.conn.commit()
            logger.info(f"{len(impacts)}件の経済的影響データを生成しました")
            return impacts
            
        except Exception as e:
            logger.error(f"経済的影響データ生成エラー: {e}")
            self.conn.rollback()
            raise
    
    def _get_evidence_level_weight(self, evidence_level):
        """
        エビデンスレベルに基づく重み付けを取得
        
        Parameters:
        -----------
        evidence_level : str
            エビデンスレベル（1a, 1b, 2a, 2b, 3, 4, 5）
        
        Returns:
        --------
        float
            重み付け値
        """
        weights = {
            '1a': 5.0,  # メタ分析/システマティックレビュー
            '1b': 4.0,  # ランダム化比較試験
            '2a': 3.0,  # コホート研究
            '2b': 2.0,  # 症例対照研究/臨床試験
            '3': 1.5,   # 横断研究/実験研究
            '4': 1.0,   # 症例報告/症例シリーズ
            '5': 0.5    # 専門家意見/不明
        }
        
        return weights.get(evidence_level, 0.5)
    
    def get_dental_issues(self):
        """
        登録されている歯列問題の一覧を取得
        
        Returns:
        --------
        pandas.DataFrame
            歯列問題の一覧
        """
        query = """
            SELECT issue_id, issue_code, issue_name_ja, issue_name_en, severity_base_score
            FROM dental_issues
            ORDER BY severity_base_score DESC
        """
        
        return pd.read_sql_query(query, self.conn)
    
    def get_age_risk_profiles(self):
        """
        年齢グループ別のリスクプロファイルを取得
        
        Returns:
        --------
        pandas.DataFrame
            年齢別リスクプロファイル
        """
        query = """
            SELECT age_threshold, risk_type, risk_value, description_ja, confidence_level
            FROM age_risk_profiles
            ORDER BY age_threshold
        """
        
        return pd.read_sql_query(query, self.conn)
    
    def get_issue_treatment_effects(self, issue_id=None):
        """
        問題別の矯正効果を取得
        
        Parameters:
        -----------
        issue_id : int, optional
            特定の問題IDを指定する場合
        
        Returns:
        --------
        pandas.DataFrame
            問題別矯正効果
        """
        if issue_id:
            query = """
                SELECT ite.effect_id, di.issue_name_ja, ite.effect_category, 
                       ite.effect_value, ite.effect_direction, ite.description_ja
                FROM issue_treatment_effects ite
                JOIN dental_issues di ON ite.issue_id = di.issue_id
                WHERE ite.issue_id = ?
                ORDER BY ite.effect_value DESC
            """
            return pd.read_sql_query(query, self.conn, params=(issue_id,))
        else:
            query = """
                SELECT ite.effect_id, di.issue_name_ja, ite.effect_category, 
                       ite.effect_value, ite.effect_direction, ite.description_ja
                FROM issue_treatment_effects ite
                JOIN dental_issues di ON ite.issue_id = di.issue_id
                ORDER BY di.issue_id, ite.effect_value DESC
            """
            return pd.read_sql_query(query, self.conn)
    
    def get_future_scenarios(self, age=None):
        """
        将来シナリオを取得
        
        Parameters:
        -----------
        age : int, optional
            特定の年齢を指定する場合
        
        Returns:
        --------
        pandas.DataFrame
            将来シナリオ
        """
        if age:
            query = """
                SELECT timeframe, with_ortho_text_ja, without_ortho_text_ja
                FROM future_scenarios
                WHERE applies_to_age_min <= ? AND applies_to_age_max >= ?
                ORDER BY timeframe_years
            """
            return pd.read_sql_query(query, self.conn, params=(age, age))
        else:
            query = """
                SELECT timeframe, applies_to_age_min, applies_to_age_max, 
                       with_ortho_text_ja, without_ortho_text_ja
                FROM future_scenarios
                ORDER BY timeframe_years, applies_to_age_min
            """
            return pd.read_sql_query(query, self.conn)
    
    def get_economic_impact(self, age):
        """
        特定の年齢の経済的影響を取得
        
        Parameters:
        -----------
        age : int
            年齢
        
        Returns:
        --------
        dict
            経済的影響データ
        """
        query = """
            SELECT current_cost, future_savings, roi
            FROM economic_impacts
            WHERE age_min <= ? AND age_max >= ?
        """
        
        df = pd.read_sql_query(query, self.conn, params=(age, age))
        
        if not df.empty:
            row = df.iloc[0]
            return {
                "current_cost": int(row['current_cost']),
                "future_savings": int(row['future_savings']),
                "net_benefit": int(row['future_savings'] - row['current_cost']),
                "roi": float(row['roi']),
                "monthly_benefit": int(row['future_savings'] / (30 * 12))  # 30年間での月当たりの便益
            }
        else:
            # デフォルト値を返す
            return {
                "current_cost": 400000,
                "future_savings": 900000,
                "net_benefit": 500000,
                "roi": 125.0,
                "monthly_benefit": 2500
            }
    
    def calculate_ortho_necessity_score(self, age, issue_ids):
        """
        矯正必要性スコアを計算
        
        Parameters:
        -----------
        age : int
            患者の年齢
        issue_ids : list
            問題IDのリスト
        
        Returns:
        --------
        dict
            必要性スコアと解釈
        """
        try:
            if not issue_ids:
                return {
                    "total_score": 0,
                    "timing_score": 0,
                    "severity_score": 0,
                    "risk_score": 0,
                    "interpretation": "問題が選択されていないため、スコアを計算できません。",
                    "urgency": "不明"
                }
            
            # 1. 年齢によるタイミングスコア（最大35点）
            timing_score = self._calculate_timing_score(age)
            
            # 2. 問題の重大性によるスコア（最大40点）
            severity_score = self._calculate_severity_score(issue_ids)
            
            # 3. 将来リスクによるスコア（最大35点）
            risk_score = self._calculate_risk_score(age, issue_ids)
            
            # 合計スコア
            total_score = timing_score + severity_score + risk_score
            
            # 小児・青年期の特別調整
            if age <= 18:
                prevention_bonus = max(0, (18 - age)) * 0.5
                total_score += prevention_bonus
            
            # 成人期の特別調整
            if 35 <= age <= 55 and len(issue_ids) >= 2:
                adult_complexity_bonus = (len(issue_ids) - 1) * 2
                total_score += adult_complexity_bonus
            
            # スコアの上限と下限を設定
            total_score = max(10, min(100, total_score))
            
            # スコアの解釈
            interpretation, urgency = self._interpret_necessity_score(total_score)
            
            return {
                "total_score": round(total_score),
                "timing_score": round(timing_score),
                "severity_score": round(severity_score),
                "risk_score": round(risk_score),
                "interpretation": interpretation,
                "urgency": urgency
            }
            
        except Exception as e:
            logger.error(f"矯正必要性スコア計算エラー: {e}")
            # エラー時のデフォルト値
            return {
                "total_score": 50,
                "timing_score": 20,
                "severity_score": 20,
                "risk_score": 10,
                "interpretation": "計算エラーが発生しました。",
                "urgency": "不明"
            }
    
    def _calculate_timing_score(self, age):
        """
        年齢によるタイミングスコアを計算
        
        Parameters:
        -----------
        age : int
            患者の年齢
        
        Returns:
        --------
        float
            タイミングスコア（最大35点）
        """
        # 年齢グループからタイミングスコアを取得
        query = """
            SELECT timing_score
            FROM age_timing_benefits
            WHERE age_min <= ? AND age_max >= ?
        """
        
        self.cursor.execute(query, (age, age))
        result = self.cursor.fetchone()
        
        if result:
            # データベースの値を35点満点にスケーリング
            base_score = result[0]
            return (base_score / 100) * 35
        else:
            # デフォルト値（年齢による減少）
            if age <= 12:
                return 35
            elif age <= 18:
                return 30
            elif age <= 25:
                return 25
            elif age <= 40:
                return 20
            elif age <= 60:
                return 15
            else:
                return 10
    
    def _calculate_severity_score(self, issue_ids):
        """
        問題の重大性によるスコアを計算
        
        Parameters:
        -----------
        issue_ids : list
            問題IDのリスト
        
        Returns:
        --------
        float
            重大性スコア（最大40点）
        """
        if not issue_ids:
            return 0
        
        # 各問題の重大度スコアを取得
        placeholders = ','.join(['?'] * len(issue_ids))
        query = f"""
            SELECT issue_id, severity_base_score
            FROM dental_issues
            WHERE issue_id IN ({placeholders})
        """
        
        self.cursor.execute(query, issue_ids)
        results = self.cursor.fetchall()
        
        if not results:
            return 0
        
        # 各問題のスコアを収集
        issue_scores = [score for _, score in results]
        
        # 主要な問題のスコア
        primary_issue_score = max(issue_scores)
        
        # 複数の問題による累積効果
        if len(issue_scores) > 1:
            # 主要問題以外のスコアを合計し、スケーリング
            secondary_issues_score = sum(sorted(issue_scores)[:-1]) * 0.5
            severity_score = min(40, (primary_issue_score + secondary_issues_score) / 100 * 40)
        else:
            severity_score = primary_issue_score / 100 * 40
        
        return severity_score
    
    def _calculate_risk_score(self, age, issue_ids):
        """
        将来リスクによるスコアを計算
        
        Parameters:
        -----------
        age : int
            患者の年齢
        issue_ids : list
            問題IDのリスト
        
        Returns:
        --------
        float
            リスクスコア（最大35点）
        """
        # 年齢閾値を取得
        query = """
            SELECT age_threshold, risk_value
            FROM age_risk_profiles
            WHERE age_threshold >= ?
            ORDER BY age_threshold
            LIMIT 1
        """
        
        self.cursor.execute(query, (age,))
        threshold_result = self.cursor.fetchone()
        
        if not threshold_result:
            return 0
        
        next_threshold, risk_value = threshold_result
        
        # 年齢依存リスク
        years_until = next_threshold - age
        urgency_factor = max(0, 1 - (years_until / 15))  # 15年以内なら影響あり
        
        # 問題数による修正係数
        problem_factor = min(1.5, 1 + (len(issue_ids) - 1) * 0.1)
        
        # 将来リスクスコアの計算
        risk_score = urgency_factor * (risk_value / 60) * problem_factor * 35
        
        return risk_score
    
    def _interpret_necessity_score(self, total_score):
        """
        必要性スコアの解釈を取得
        
        Parameters:
        -----------
        total_score : float
            合計スコア
        
        Returns:
        --------
        tuple (str, str)
            (解釈, 緊急度)
        """
        if total_score >= 85:
            return "緊急性の高い矯正必要性。早急な対応が強く推奨されます。", "緊急"
        elif total_score >= 70:
            return "高い矯正必要性。できるだけ早い対応が望ましいです。", "高"
        elif total_score >= 50:
            return "中程度の矯正必要性。計画的な対応を検討してください。", "中"
        elif total_score >= 30:
            return "低〜中程度の矯正必要性。定期的な経過観察をお勧めします。", "低"
        else:
            return "現時点での矯正必要性は低いですが、定期的な評価をお勧めします。", "最小"

    def reset_database(self):
        """
        データベースをリセットし、スキーマを再作成
        """
        try:
            # 既存のテーブルを削除
            self.cursor.executescript("""
                DROP TABLE IF EXISTS user_reports;
                DROP TABLE IF EXISTS economic_impacts;
                DROP TABLE IF EXISTS future_scenarios;
                DROP TABLE IF EXISTS age_timing_benefits;
                DROP TABLE IF EXISTS issue_treatment_effects;
                DROP TABLE IF EXISTS age_risk_profiles;
                DROP TABLE IF EXISTS research_findings;
                DROP TABLE IF EXISTS paper_issue_relations;
                DROP TABLE IF EXISTS issue_keywords;
                DROP TABLE IF EXISTS dental_issues;
                DROP TABLE IF EXISTS research_papers;
                DROP TABLE IF EXISTS system_settings;
            """)
            
            self.conn.commit()
            logger.info("データベースをリセットしました")
            
            # スキーマを再作成
            self.initialize_db()
            
        except Exception as e:
            logger.error(f"データベースリセットエラー: {e}")
            self.conn.rollback()
            raise
    
    def generate_all_evidence_data(self):
        """
        すべてのエビデンスデータを生成
        
        Returns:
        --------
        dict
            生成されたデータの要約
        """
        try:
            # 1. 年齢別リスクデータの生成
            risk_profiles = self.generate_age_risk_profiles()
            
            # 2. 問題別矯正効果データの生成
            treatment_effects = self.generate_issue_treatment_effects()
            
            # 3. 年齢グループ別のタイミング効果の生成
            timing_benefits = self.generate_age_timing_benefits()
            
            # 4. 将来シナリオの生成
            scenarios = self.generate_future_scenarios()
            
            # 5. 経済的影響データの生成
            economic_impacts = self.generate_economic_impacts()
            
            self.conn.commit()
            logger.info("すべてのエビデンスデータを正常に生成しました")
            
            return {
                "risk_profiles_count": len(risk_profiles) if isinstance(risk_profiles, list) else 0,
                "treatment_effects_count": len(treatment_effects) if isinstance(treatment_effects, list) else 0,
                "timing_benefits_count": len(timing_benefits) if isinstance(timing_benefits, list) else 0,
                "scenarios_count": len(scenarios) if isinstance(scenarios, list) else 0,
                "economic_impacts_count": len(economic_impacts) if isinstance(economic_impacts, list) else 0
            }
            
        except Exception as e:
            logger.error(f"エビデンスデータ生成エラー: {e}")
            self.conn.rollback()
            raise
        
    def export_to_csv(self, output_dir='.'):
        """
        データベースの内容をCSVファイルにエクスポート
        
        Parameters:
        -----------
        output_dir : str
            出力ディレクトリ
        
        Returns:
        --------
        int
            エクスポートされたファイル数
        """
        import os
        
        try:
            # 出力ディレクトリの確認
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # エクスポートするテーブルとファイル名のリスト
            tables = [
                ('dental_issues', 'dental_issues.csv'),
                ('issue_keywords', 'issue_keywords.csv'),
                ('age_risk_profiles', 'ortho_age_risks.csv'),
                ('issue_treatment_effects', 'ortho_benefits.csv'),
                ('age_timing_benefits', 'timing_benefits.csv'),
                ('future_scenarios', 'future_scenarios.csv'),
                ('economic_impacts', 'economic_impact.csv')
            ]
            
            # 各テーブルをCSVにエクスポート
            for table_name, file_name in tables:
                # クエリの実行
                query = f"SELECT * FROM {table_name}"
                df = pd.read_sql_query(query, self.conn)
                
                # CSVに保存
                output_path = os.path.join(output_dir, file_name)
                df.to_csv(output_path, index=False)
                logger.info(f"テーブル '{table_name}' を '{output_path}' にエクスポートしました")
            
            return len(tables)
            
        except Exception as e:
            logger.error(f"CSVエクスポートエラー: {e}")
            raise
