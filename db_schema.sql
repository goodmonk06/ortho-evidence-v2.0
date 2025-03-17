-- 1. 研究論文テーブル
CREATE TABLE research_papers (
    paper_id INTEGER PRIMARY KEY,
    pmid TEXT,                    -- PubMed ID
    title TEXT NOT NULL,
    authors TEXT,
    publication_year INTEGER,
    journal TEXT,
    doi TEXT,                     -- Digital Object Identifier
    url TEXT,                     -- PubMed URL
    abstract TEXT,                -- 論文の抄録
    keywords TEXT,                -- キーワード（カンマ区切り）
    mesh_terms TEXT,              -- MeSH用語（カンマ区切り）
    study_type TEXT,              -- 研究タイプ（meta-analysis, cohort-study, case-control等）
    evidence_level TEXT,          -- エビデンスレベル（1a, 1b, 2a, 2b, 3, 4, 5）
    sample_size INTEGER,          -- サンプルサイズ
    confidence_interval TEXT,     -- 信頼区間
    target_age_group TEXT,        -- 対象年齢グループ
    imported_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 取り込み日時
    UNIQUE(doi)
);

-- 2. 歯列問題マスターテーブル
CREATE TABLE dental_issues (
    issue_id INTEGER PRIMARY KEY,
    issue_code TEXT NOT NULL,      -- 問題コード（システム内部での識別用）
    issue_name_ja TEXT NOT NULL,   -- 日本語名（「叢生」など）
    issue_name_en TEXT NOT NULL,   -- 英語名（「Crowding」など）
    description_ja TEXT,           -- 日本語の説明
    description_en TEXT,           -- 英語の説明
    severity_base_score INTEGER,   -- 基本的な重大度スコア（100点満点）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(issue_code)
);

-- 3. 歯列問題検索キーワードテーブル（問題の分類精度向上用）
CREATE TABLE issue_keywords (
    keyword_id INTEGER PRIMARY KEY,
    issue_id INTEGER NOT NULL,     -- dental_issuesテーブルへの参照
    keyword TEXT NOT NULL,         -- 検索キーワード（「crowding」「dental crowding」など）
    language TEXT DEFAULT 'en',    -- 言語（en, ja等）
    weight REAL DEFAULT 1.0,       -- キーワードの重み（重要なキーワードほど大きい値）
    FOREIGN KEY (issue_id) REFERENCES dental_issues(issue_id),
    UNIQUE(issue_id, keyword, language)
);

-- 4. 研究論文と歯列問題の関連テーブル
CREATE TABLE paper_issue_relations (
    relation_id INTEGER PRIMARY KEY,
    paper_id INTEGER NOT NULL,
    issue_id INTEGER NOT NULL,
    relevance_score REAL DEFAULT 1.0,  -- 関連性スコア（自動分類時に使用）
    is_primary BOOLEAN DEFAULT FALSE,  -- 主要な問題かどうか
    FOREIGN KEY (paper_id) REFERENCES research_papers(paper_id),
    FOREIGN KEY (issue_id) REFERENCES dental_issues(issue_id),
    UNIQUE(paper_id, issue_id)
);

-- 5. 研究結果（リスク・効果）テーブル
CREATE TABLE research_findings (
    finding_id INTEGER PRIMARY KEY,
    paper_id INTEGER NOT NULL,
    issue_id INTEGER NOT NULL,
    finding_type TEXT NOT NULL,       -- 「risk」（リスク）または「benefit」（メリット）
    description_ja TEXT NOT NULL,     -- 日本語の説明
    description_en TEXT,              -- 英語の説明
    effect_value REAL,                -- 効果量・リスク値（%や倍率）
    effect_direction TEXT,            -- 効果の方向（「increase」「decrease」など）
    confidence_interval TEXT,         -- 信頼区間
    p_value REAL,                     -- p値
    applies_to_age_min INTEGER,       -- 適用される最小年齢
    applies_to_age_max INTEGER,       -- 適用される最大年齢
    FOREIGN KEY (paper_id) REFERENCES research_papers(paper_id),
    FOREIGN KEY (issue_id) REFERENCES dental_issues(issue_id)
);

-- 6. 年齢グループ別リスクテーブル（動的に生成される）
CREATE TABLE age_risk_profiles (
    profile_id INTEGER PRIMARY KEY,
    age_threshold INTEGER NOT NULL,    -- 年齢閾値
    risk_type TEXT NOT NULL,           -- リスクタイプ（tooth_loss, periodontal, etc）
    risk_value REAL NOT NULL,          -- リスク値（%）
    description_ja TEXT NOT NULL,      -- 日本語の説明
    description_en TEXT,               -- 英語の説明
    calculated_from TEXT,              -- 計算元（論文IDリスト等）
    confidence_level REAL,             -- 信頼度（エビデンスの強さ）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(age_threshold, risk_type)
);

-- 7. 問題別矯正効果テーブル（動的に生成される）
CREATE TABLE issue_treatment_effects (
    effect_id INTEGER PRIMARY KEY,
    issue_id INTEGER NOT NULL,
    effect_category TEXT NOT NULL,     -- 効果カテゴリ（caries_risk, periodontal_risk等）
    effect_value REAL NOT NULL,        -- 効果値（%）
    effect_direction TEXT NOT NULL,    -- 方向（increase/decrease）
    description_ja TEXT NOT NULL,      -- 日本語の説明
    description_en TEXT,               -- 英語の説明
    calculated_from TEXT,              -- 計算元（論文IDリスト等）
    confidence_level REAL,             -- 信頼度（エビデンスの強さ）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (issue_id) REFERENCES dental_issues(issue_id),
    UNIQUE(issue_id, effect_category)
);

-- 8. 年齢グループ別矯正タイミングテーブル（動的に生成される）
CREATE TABLE age_timing_benefits (
    timing_id INTEGER PRIMARY KEY,
    age_group_code TEXT NOT NULL,      -- 年齢グループコード
    age_min INTEGER,                   -- 最小年齢
    age_max INTEGER,                   -- 最大年齢
    age_group_ja TEXT NOT NULL,        -- 日本語の年齢グループ名
    age_group_en TEXT,                 -- 英語の年齢グループ名
    benefit_text_ja TEXT NOT NULL,     -- 日本語のメリット説明
    benefit_text_en TEXT,              -- 英語のメリット説明
    recommendation_level TEXT NOT NULL, -- 推奨レベル
    timing_score INTEGER NOT NULL,     -- タイミングスコア
    calculated_from TEXT,              -- 計算元（論文IDリスト等）
    confidence_level REAL,             -- 信頼度（エビデンスの強さ）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(age_group_code)
);

-- 9. 将来シナリオテーブル（動的に生成される）
CREATE TABLE future_scenarios (
    scenario_id INTEGER PRIMARY KEY,
    timeframe TEXT NOT NULL,           -- 時間枠（例：「5年後」）
    timeframe_years INTEGER,           -- 年数に変換
    with_ortho_text_ja TEXT NOT NULL,  -- 日本語の「矯正した場合」テキスト
    with_ortho_text_en TEXT,           -- 英語の「矯正した場合」テキスト
    without_ortho_text_ja TEXT NOT NULL, -- 日本語の「矯正しなかった場合」テキスト
    without_ortho_text_en TEXT,        -- 英語の「矯正しなかった場合」テキスト
    applies_to_issue_ids TEXT,         -- 適用される問題ID（カンマ区切り）
    applies_to_age_min INTEGER,        -- 適用される最小年齢
    applies_to_age_max INTEGER,        -- 適用される最大年齢
    calculated_from TEXT,              -- 計算元（論文IDリスト等）
    confidence_level REAL,             -- 信頼度（エビデンスの強さ）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(timeframe, applies_to_age_min, applies_to_age_max)
);

-- 10. 経済的影響テーブル（動的に生成される）
CREATE TABLE economic_impacts (
    impact_id INTEGER PRIMARY KEY,
    age_group_code TEXT NOT NULL,      -- 年齢グループコード
    age_min INTEGER,                   -- 最小年齢
    age_max INTEGER,                   -- 最大年齢
    age_group_ja TEXT NOT NULL,        -- 日本語の年齢グループ名
    age_group_en TEXT,                 -- 英語の年齢グループ名
    current_cost INTEGER NOT NULL,     -- 現在の矯正費用（円）
    future_savings INTEGER NOT NULL,   -- 将来的な医療費削減額（円）
    roi REAL NOT NULL,                 -- 投資収益率（%）
    calculation_basis TEXT,            -- 計算根拠
    confidence_level REAL,             -- 信頼度（エビデンスの強さ）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(age_group_code)
);

-- 11. ユーザーレポート履歴テーブル（オプション）
CREATE TABLE user_reports (
    report_id INTEGER PRIMARY KEY,
    session_id TEXT,                   -- セッションID
    patient_age INTEGER NOT NULL,      -- 患者年齢
    patient_gender TEXT,               -- 患者性別
    selected_issues TEXT NOT NULL,     -- 選択された問題（JSONまたはカンマ区切り）
    necessity_score INTEGER,           -- 必要性スコア
    recommendations TEXT,              -- 提供された推奨事項
    report_html TEXT,                  -- 生成されたHTMLレポート
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 12. システム設定テーブル
CREATE TABLE system_settings (
    setting_id INTEGER PRIMARY KEY,
    setting_key TEXT NOT NULL,
    setting_value TEXT,
    setting_description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(setting_key)
);

-- サンプルデータ：歯列問題マスター
INSERT INTO dental_issues (issue_code, issue_name_ja, issue_name_en, severity_base_score) VALUES
('crowding', '叢生', 'Crowding', 70),
('open_bite', '開咬', 'Open Bite', 65),
('deep_bite', '過蓋咬合', 'Deep Bite', 60),
('crossbite', '交叉咬合', 'Crossbite', 65),
('overjet', '上顎前突', 'Overjet', 55),
('underbite', '下顎前突', 'Underbite', 60),
('spacing', '空隙歯列', 'Spacing', 45),
('midline_deviation', '正中線偏位', 'Midline Deviation', 40),
('impacted_teeth', '埋伏歯', 'Impacted Teeth', 75),
('rotated_teeth', '歯の回転', 'Rotated Teeth', 50);

-- サンプルデータ：問題キーワード（叢生の例）
INSERT INTO issue_keywords (issue_id, keyword, weight) VALUES
(1, 'crowding', 1.0),
(1, 'dental crowding', 1.1),
(1, 'tooth crowding', 1.0),
(1, 'crowded teeth', 0.9),
(1, 'malocclusion type I with crowding', 1.2);
