# 「世の中の思考の流れ」研究プロジェクト — Cursor実装Plan 正本

## 1. Plan情報

| 項目 | 内容 |
|---|---|
| 対象requirements版 | `docs/requirements.md` 1.0（基準日 2026-08-23） |
| Plan版 | 1.0 |
| 対象期間 | 2026-08-23〜2026-09-18（初回PoCスプリント） |
| 最終評価期限 | 2026-09-20より前。本Planでは2026-09-18を内部完了期限とする |
| Source of Truth | `docs/requirements.md`。本Planは要件を変更せず、実施順序と設計境界を定める |
| 実装主体 | Cursor（Repository変更・実装・テスト・デバッグ） |
| 設計・レビュー | Codex 5.6 Sol（設計判断・Research Methodology・Milestone Review） |
| 外部設定・最終判断 | Human（SPO / Entra / Azure / GCP設定、Trial確認、Promote、継続判断） |
| Codex実行制約 | Codex Plus / GPT-5.6 Solの利用保証は2026-09-01まで。Codex-criticalな設計・方法論は2026-08-31までにFreezeする |

### 1.1 優先順位とラベル

MUSTおよび期限依存の検証を最優先する。SHOULDはMUST経路の安定後、COULDは余力と価値が確認された場合だけ着手する。作業ラベルは次のとおりとする。

- `codex-design`：高度設計、研究方法、判定規則の大枠
- `cursor-implement`：Repository、Python、データ、連携、テストの実装
- `human-action`：管理画面、権限同意、Trial、手動SPO / Copilot操作、研究判断
- `codex-review`：要件適合、研究妥当性、再現性、安全性のダブルチェック

## 2. Executive Summary

最初に、Repositoryの公開安全基盤とローカルの最小データ経路を作る一方、期限依存のM365 Trial、SPO / Copilot、Graph / Entra、GCP課金設定を早期Spikeで確認する。次に、4センサーの規約・取得可能性を少量サンプルで判定し、少なくとも1つの経路で4か国 × 2テーマ × 必要期間を分析可能と見込めるかをResearch Feasibility Gateで確認する。Research Methodology Gate A〜Eで観測単位、proxy、時刻、辞書、国判定を凍結し、2026-08-31にCodex Architecture Freeze Reviewを完了する。Gate通過前に大規模backfill、分布指標、国別Canonicalを本実装しない。実装の中心はRawを不変に保持するローカル `Python + DuckDB + Parquet` 経路であり、SPO、BigQuery、Azure、GitHub Actionsは交換・停止可能な境界に置く。SharePoint側はSourceを1操作でCaptureし、利用後に選択的Promoteする最小Hubに限定する。BigQuery比較は分析完成後まで放置せず、アクセス確認をM2、同等クエリ実行をM9で2026-09-10までに完了する。Azure Blob / Azure AI Foundryは採否を先に記録し、採用したものだけを検証する。専用Web UI、大量Card生成、汎用Connector Framework、Knowledge Graphは作らない。各Milestoneの証拠をPortfolio文書へ逐次反映し、09-17までに期限前の最終週次run、2026-09-18に三軸判断を完了する。

## 3. Architecture Direction

### 3.1 定量観測経路

```text
Public Sources
    │
    ├── Research sensor
    ├── Developer sensor
    ├── Company sensor
    └── General-interest sensor
            ↓
     Thin source connectors
            ↓
  Immutable Raw + run manifest
  (local Parquet / DuckDB catalog)
            ↓
  Methodology Gates A–E
            ↓
  Weekly Canonical datasets
  (local source of truth)
            ↓
  Within-sensor analysis first
            ↓
  Analysis results + quality report
            ↓
  Findings artifacts
            ↓
  SharePoint Current Findings
```

### 3.2 Research Hub運用経路

```text
Public Source discovery
          ↓
One-action Capture
          ↓
SPO Sources library ───────→ Copilot search / compare / summarize
          │                              ↓
          │                         Actual research use
          │                              ↓
          └──────────────────→ Selective Promote
                                         ↓
                                  Research Cards
```

定量観測経路とResearch Hub運用経路は連携するが、同一Pipelineにはしない。公開資料のCaptureやCopilot利用は、データAPIのバックフィル完了を待たずに成立させる。定量成果のSPO還流は、ローカル生成物の手動投入を常にフォールバックとして残す。

### 3.3 コンポーネント責務

| 領域 | 責務 | 正本性 / 依存性 |
|---|---|---|
| Local Raw | 取得元粒度、原取得値、取得証跡を不変に保存 | ローカル正本。外部サービスに依存しない |
| Local Canonical | Gateで確定した規則により週次へ正規化 | ローカル正本。Rawから再生成可能 |
| Local Analysis | センサー内比較、尺度を揃えた限定的横断比較、品質評価 | ローカル主経路 |
| SPO Research Hub | Source保管・参照、Copilot利用、選択的Card化、Findings表示 | 人向け利用・可視化面。分析正本ではない |
| Graph / Entra | SPOとの最小統合と認証・権限知見 | 停止可能。手動SPO操作へフォールバック |
| BigQuery | DuckDBと同一または同等分析の比較検証 | 一回以上の必須検証。主基盤ではない |
| Azure Blob | Parquet等の副本候補 | COULD。採否判断後のみ |
| Azure AI Foundry | Card生成・分類・解釈の補助候補 | COULD。観測事実を生成しない |
| GitHub Actions | 安定済み週次処理の実行候補 | SHOULD。ローカル手動実行を残す |

### 3.4 境界方針

- Connectorはデータ源ごとの薄いAdapterとし、共通化は実行結果、ログ、Raw保存契約に限定する。汎用Plugin / Factory基盤を作らない。
- 外部API障害は当該センサーの実行結果を`fetch_failure`にし、他センサーと過去Rawを利用した処理を継続する。
- SPO公開面へ出すのは公開可能なSource参照、Research Card、集計済みFindingsであり、Secretやテナント固有情報を含めない。
- BigQueryへ渡すのは比較に必要な公開可能Canonicalまたはサンプルに限定し、正本を移さない。
- AI補助出力にはモデル、実行日時、費用、入力範囲、human review状態を付け、観測事実と分離する。

## 4. Critical Path

### 4.1 期限までの最短経路

```text
M1 Public-safe repository + local skeleton
 ├─→ M2 Deadline-dependent external readiness
 │     ├─→ M3 SPO Hub + Capture/Use/Promote
 │     └─→ M4 Graph/Entra minimum validation
 └─→ M5 Sensor go/no-go + licensing
          ↓
       Research Feasibility Gate
          ↓
       M6 Methodology Gates A–E + contract freeze
          ↓
       M7 Raw ingestion + backfill
          ↓
       M8 Canonical + reproducible analysis
          ├─→ M9 BigQuery parity comparison
          └─→ M10 Weekly operation / optional branches
                         ↓
                   M11 Three-axis acceptance and decision
```

M3 / M4はM2のM365確認後、M5はM1の公開安全方針が決まり次第開始できる。Research Feasibility Gateが不成立なら、4センサーの可否記録は残すがM7の大規模backfillへ進まず、Research MUSTを`blocked`としてHumanへ返す。M7はFeasibility GateとGate Dの辞書レビュー後に本バックフィルへ進み、M8の国別CanonicalはGate Eの規則凍結後に進む。M9はM8の最小分析契約が固定され次第着手し、全Finding完成を待たない。

### 4.2 内部期限

| 期間 | 到達点 | Deadline理由 |
|---|---|---|
| 08-23〜08-25 | M1完了、M2開始 | 公開安全と外部アクセス阻害を初動で可視化 |
| 08-23〜08-27 | M2完了 | Trial、課金、BigQueryアクセスの致命的阻害を前倒し |
| 08-24〜08-30 | M3 / M4完了 | SPO / Copilot / GraphをTrial後半へ残さない |
| 08-23〜08-28 | M5とResearch Feasibility Gate完了 | 取得不能センサーとResearch MUST成立不能を大規模backfill前に判定 |
| 08-27〜08-31 | M6 Gate A〜E、Data Contract、Codex Architecture Freeze Review完了 | Codex利用保証内に尺度・時刻・国・辞書・分母をFreeze |
| 09-01〜09-06 | M7完了 | 再実行・代替取得の余白を確保 |
| 09-05〜09-10 | M8 / M9完了 | ResearchとBigQueryのMUSTを期限10日前までに成立 |
| 09-09〜09-17 | M10完了 | 初回backfill後の各週次窓を実行し、09-20を含む最終週のrunも評価前に完了。任意機能は先に打ち切れる |
| 09-12〜09-18 | M11完了 | 外部レビューと継続判断の修正余白を2日以上確保 |

### 4.3 MUSTを守る削減順

遅延時は、(1) Azure AI Foundry、(2) Azure Blob、(3) Researcher / Analyst / Power Automateの追加検証、(4) GitHub Actions、(5)追加指標・追加Source候補、(6)Streamlit等のUIの順で削る。4センサー可否記録、SPO / Copilot / Graph検証、ローカルRaw / Canonical、1件の再現分析、BigQuery比較、公開安全、三軸判断は削らない。

## 5. Early Spikes / Validation Gates

### 5.1 外部サービスSpike

| Spike | Purpose | Requirement IDs | Method | Pass criteria | Fail fallback | Owner |
|---|---|---|---|---|---|---|
| S1 M365 Trial entitlement | 実テナントで候補機能の表示・利用可否を確定 | 14.1、FR-INT-001〜003、AC-M365-002 | Humanが管理画面と各機能入口を確認し、日付・契約・可否・証拠を記録 | SPO、必要なPages / Lists / Libraryが利用でき、Copilot試験経路が特定される | 利用不能機能は見送り。SPO手動またはローカル成果物で継続し制約を成果化 | `human-action`, `codex-review` |
| S2 SharePoint / Copilot | CardなしSourceの検索・要約可能性とCapture負荷を確認 | FR-HUB-001〜008、FR-INT-001、AC-HUB-001〜005、AC-HUB-003 | シード資料の公開参照または許可されたファイルでCapture、検索、比較、要約を小規模試行 | 1操作Capture候補があり、CardなしSource利用範囲と制約が記録される | 手動アップロード / リンクとPagesへの手動還流を採用。Copilot不能はTrial制約として記録 | `human-action`, `cursor-implement`, `codex-review` |
| S3 Graph / Entra | 認証・最小権限・管理者同意の実現性を早期判定 | FR-INT-002〜003、AC-M365-001 | アプリ登録候補と委任 / アプリ権限を比較し、最小の許可済みreadまたはwriteを試行 | 最小操作が成功、または再現可能な阻害条件と継続判断が得られる | 手動SPO投入。PnP等はGraph不足が具体化した場合のみ比較 | `codex-design`, `cursor-implement`, `human-action`, `codex-review` |
| S4 Four-sensor availability | 4系統のデータ・地理・時刻・期間の取得可能性を判定 | FR-DATA-001、AC-DATA-001、TBD-001 | 候補ごとに少量取得、4か国属性、2022-11-30以後の履歴、レート制限を表にする | 各系統にgo候補、または規約と技術根拠を伴うno-go / fallbackがある | 同系統の代替公開API / download / bounded manual sample。無理なscrapingはしない | `codex-design`, `cursor-implement`, `codex-review` |
| S5 Data usage / licensing | 保存、再配布、公開サンプルの境界を確定 | FR-DATA-001、17.2、AC-SEC-001 | ToS、API terms、license、robots / download条件を取得日付きで記録 | Raw保存可否、Public Repositoryへの再配布可否、引用方法が各採用候補で明確 | Raw非公開、取得手順と合成 / 最小サンプルのみ公開。不可なら候補を見送る | `human-action`, `codex-review` |
| S6 BigQuery access / cost | 比較実行を期限前に可能にする | FR-ANL-005、14.3、AC-ANL-003 | Project / dataset作成権限、Credit期限、billing / quota、少量queryを確認 | 少量データのquery成功、費用確認方法と比較投入経路が決まる | 権限阻害を直ちにHumanへ返す。解消待ち中もDuckDB実装を継続 | `cursor-implement`, `human-action`, `codex-review` |
| S7 Azure budget / availability | COULDの採否前提と課金防止を確認 | 14.2、18、AC-COST-001、TBD-011〜012 | 予算 / alert可否、Foundry / Blob entitlement、想定価値を机上比較 | 採用価値がMUST作業を上回り、上限管理と利用記録方法が成立 | 不採用理由のみ記録。ローカル経路を継続 | `human-action`, `codex-design`, `codex-review` |

### 5.2 Research Methodology Gate A〜E

| Gate | Purpose | Requirement IDs | Method | Pass criteria | Fail fallback | Owner |
|---|---|---|---|---|---|---|
| A 観測単位・母集団・分母 | 異尺度の生値比較と不正な分布統計を防ぐ | FR-ANL-002〜004、12.6、15.2、TBD-009 | センサーごとにunit、population、denominator、aggregation、normalization、欠損、unknown、比較可能範囲をDecision Record化 | 各センサー内で意味のある週次測定が定義され、横断比較可否が明示される | 未確定センサーはRawのみ保持。分布指標の本実装対象から外す | `codex-design`, `codex-review` |
| B Sensor / social layer proxy | センサーをmicro / meso / macroと直結させない | 12.1、15.1、TBD-010 | sensor、actor / population、social layer proxy、limitationsを分離した表をレビュー | 自動対応付けがなく、proxyとして主張可能な範囲が明示される | 社会階層ラベルを分析出力から外し、センサー別結果だけを報告 | `codex-design`, `codex-review` |
| C 時間意味 | 収録遅延を社会伝播遅延と誤認しない | FR-DATA-004、FR-ANL-003、12.6、15.2 | event / publication / observed / ingestion timeの取得可否、Canonical基準時刻、既知 / 不明lagをセンサー別に整理 | Canonicalの基準時刻とLimitationsが固定され、時刻欠損時の扱いが定義される | 先行 / 伝播主張を行わず、観測系列の同時点比較または記述に限定 | `codex-design`, `cursor-implement`, `codex-review` |
| D テーマ辞書品質 | 4言語・2テーマの誤検出を抑え、版を固定 | FR-DATA-007、12.5、AC-DATA-004、TBD-007 | positive、synonym、variant、ambiguous、exclusionを作成し、国・テーマ別サンプルを人手照合 | 初版辞書がレビュー済み、false-positive所見と版が記録される | 問題語を除外または対象を狭める。本バックフィルを開始しない | `codex-design`, `cursor-implement`, `human-action`, `codex-review` |
| E 国判定品質 | 推測禁止と複数国の再現可能集計を守る | FR-DATA-006、12.4、AC-DATA-003、TBD-008 | 一次属性のevidence、unknown、複数国Raw保持を確認し、候補集計規則の影響をサンプル比較 | 国別Canonical前に規則と版が承認され、unknown比率算出が可能 | Raw収集は継続するが国別Canonicalを凍結。国を使わない集計へ限定 | `codex-design`, `cursor-implement`, `codex-review` |

Gate A〜EのDecision Recordが揃うまで、Cursorは分布指標の本実装、国別Canonicalの確定、先行 / 伝播遅延の結論生成を開始しない。少量の探索コードはGateの判断材料に限り、成果指標として固定しない。

### 5.3 Research Feasibility Gate

| Gate | Purpose | Requirement IDs | Method | Pass criteria | Fail fallback | Owner |
|---|---|---|---|---|---|---|
| RF Research MUST feasibility | 4センサーがpartial / no-goでも、大規模backfill前に最終Research MUSTの成立見込みを確認する | 4.1、12.2、FR-ANL-003、AC-ANL-001 | M5の実サンプルとcoverage profileから、4か国 × 2テーマ × 2022-11-30以後の必要期間を比較可能な時系列として構成できる経路を少なくとも1つ示す。4センサーすべてを最終分析に使う必要はない | 1つ以上の分析経路について、国・テーマ・期間・時刻・分母・取得方法の成立見込みと未確実性が記録される | M7の大規模backfillへ進まない。4系統の可否記録は完了させ、coverageを推測補完せず、Research MUSTを`blocked`としてHumanへ返す | `codex-design`, `cursor-implement`, `human-action`, `codex-review` |

RFはM5 Exitの一部であり、Gate A〜Eを代替しない。RF通過後も、Gate A〜Eに不合格のセンサーはRaw試行に留め、CanonicalまたはFindingへ昇格させない。

### 5.4 Codex Architecture Freeze Gate

2026-08-31に、M5のsource採否とRF、M6のGate A〜E、Raw / Canonical / Analysisの概念契約、time semantics、country rule、dictionary version、population / denominatorを一括レビューする。Pass条件は、採用・見送り・未解決がDecision Recordで区別され、未解決項目にはCursorの停止条件とHuman判断先があり、09-01以後にCodexなしで実装判断を再発明しなくてよいことである。未通過の場合、M3 / M4など独立作業は継続できるが、M7の大規模backfillとM8のCanonical / 分析実装は開始しない。

## 6. Milestones

### M1 — Public-safe Repository and Local Skeleton

**目的**

独立Repositoryを公開可能な状態で開始し、外部サービスなしで設定読込、Raw保存、再現実行、テストができる最小骨格を作る。

**対応要件**

- Requirement IDs: 5.1データ基盤、16.1〜16.5、17.1〜17.3、19.1〜19.3、FR-DATA-005、FR-ANL-001
- Acceptance Criteria IDs: AC-M365-003、AC-PORT-001、AC-SEC-001の基盤部分

**依存**

- 前提Milestone: なし
- External dependency: なし

**設計判断**

- Python 3.12、`pyproject.toml`、`uv`による再現可能な依存管理を採用する。
- `src` layoutとし、Raw / Canonical / Analysis / external integrationsを責務分離する。
- Secretは環境変数とサービス側Secretへ分離し、Repositoryには`.env.example`のみ置く。
- `run_identity`は実行ごと、run manifestも実行ごとに一意とする。一方、`record_identity`は同一source record、`raw_content_identity`は同一内容を安定識別し、`canonical_snapshot_identity`は入力Raw集合・rule versions・code revisionから決定可能にする。
- Rawは追記専用とし、別runが同じ内容を取得しても既存内容を上書きしない。

**Cursor実装範囲**

- 独立Git Repositoryの初期化、公開前提のignore / attributes / license候補の準備。
- 論理構成、設定読込、CLIまたは同等のローカル実行入口、構造化ログの最小骨格。
- DuckDB catalogとParquet保存経路の疎通。DDL詳細はM6のcontract freeze後に確定する。
- pytestによる設定、run manifest、Raw非上書きの最小テスト。
- README冒頭、architecture / methodology / validation / findings / comparison文書の章立てを作る。
- Source of Truth、優先度、Raw不変、国推測禁止、sensor / proxy分離、Card任意性、外部連携任意性、報告形式だけを要約した短い`AGENTS.md`をSHOULD成果物として用意する。要件全文は複製しない。

**Human Action**

- Public Repository名、公開ライセンス、GitHub公開時期を確認する。公開前まではローカルでもよい。

**検証**

- Secretなしの環境で同じサンプル入力を2回保存し、run / manifest identityは異なり、record / Raw content identityと決定的なdata result identityは一致することを確認する。
- 外部連携を無効化してローカル処理が起動する。
- Secret scannerと公開対象ファイル一覧の初回確認を行う。

**Exit Gate**

外部サービスなしで最小runが成功し、Rawが上書きされず、公開禁止情報を含まないRepository骨格と再実行手順がある。

**Codex Review Gate**

`codex-review`で、独立性、過剰抽象化の不在、Raw不変性、Secret境界、必須文書の入口を確認する。

**作らないもの**

汎用Connector Framework、Web UI、完全DDL、全外部サービスのSDK wrapper、CI自動化は作らない。

### M2 — Deadline-dependent External Readiness

**目的**

M365 Trial、Copilot、Graph / Entra、BigQuery、Azure予算の権限・課金阻害を4週間の前半で可視化する。

**対応要件**

- Requirement IDs: 14.1〜14.3、17.3、18、FR-INT-001〜006、TBD-005、TBD-011〜014
- Acceptance Criteria IDs: AC-M365-001〜003、AC-ANL-003、AC-COST-001

**依存**

- 前提Milestone: M1の公開安全方針
- External dependency: Microsoft 365 / Entra / Azure / GCPアカウント、Human権限

**設計判断**

- S1、S3、S6、S7の結果をDecision Recordへ残す。
- Azureはこの時点では採否だけを判断し、サービス実装を開始しない。
- 認証方式・権限は最小権限Spikeの結果で選び、テナント固有値を文書へ残さない。

**Cursor実装範囲**

- 外部接続確認用の最小smoke入口と、成功 / 失敗を公開安全に記録するテンプレート。
- BigQueryの少量queryと費用確認に必要な最小検証資材。
- M365 Validation Logおよびcloud comparisonへ追記する検証テンプレート。

**Human Action**

- Trial entitlement、Copilot入口、SPO作成権限、Entraアプリ登録 / 同意可否を確認する。
- GCP Credit期限、billing / quota、BigQuery project権限を確認する。
- Azure budget / alertの設定可否を確認する。

**検証**

- S1、S3、S6、S7の各Pass criteriaまたはFail fallbackが文書化されている。
- 認証失敗ログにtoken、Tenant ID、subscription / project固有値を残していない。

**Exit Gate**

SPO / Copilot / Graph / BigQueryの実施経路または明確な阻害とフォールバックがあり、Azure任意枝の採否判断時期が確定している。

**Codex Review Gate**

期限リスク、最小権限、課金防止、COULDのMUST化がないことを確認する。

**作らないもの**

本番用Graph同期、Azure資源の一括作成、GitHub Actionsは作らない。

### M3 — SharePoint Research Hub MVP and Corpus Workflow

**目的**

最小のSPO Research Hubを作り、シード3文献で「Capture → そのまま利用 → 選択的Promote」が継続可能か検証する。

**対応要件**

- Requirement IDs: FR-HUB-001〜008、FR-INT-001、13.1〜13.3、15.4、TBD-002〜004
- Acceptance Criteria IDs: AC-HUB-001〜005、AC-M365-002

**依存**

- 前提Milestone: M2のS1 / S2開始条件
- External dependency: SPO、Copilot、シード文献の公開参照情報

**設計判断**

- Sources、Research Cards、Home、Methodology、Current Findings、M365 Validation Logに限定する。
- Card最終項目、Sourceをファイル / linkのどちらで保持するか、3状態の表現はシード試行後に凍結する。
- Captureの「1操作」は利用者の通常操作を数え、事前の管理設定を含めない。追加後の分類は必須にしない。

**Cursor実装範囲**

- SPO設定手順、構成記録、公開可能なテンプレート、手動投入用成果物をRepositoryへ用意する。
- Research Cardの最小候補と状態遷移の検証記録を作る。
- Copilot試験ケースと結果記録様式を用意する。
- Findingsをローカルから手動でPagesへ戻す最小経路を文書化する。

**Human Action**

- 研究専用Site、Library、List、4 Pagesを実環境で作成する。
- シード3文献をCaptureし、Cardなし利用、少なくとも1件のUsed、価値がある場合のみPromotedを実施する。
- Copilotで検索、比較、要約、原典確認を試し、2週間休止想定の再開試験を行う。

**検証**

- 1操作Capture、Cardなし利用、選択的Promote、原典参照を手動確認する。
- 必須入力数、操作数、失敗、Copilotの可視範囲を記録する。
- 未整理Sourceを残したまま新規利用を再開できることを確認する。

**Exit Gate**

AC-HUB-001〜005の証拠があり、TBD-002〜004が実利用に基づき決定または見送りされ、Card大量作成を要求しないHubが動作する。

**Codex Review Gate**

利用継続性、原典とCardの責務分離、Copilot結果の過大評価、ページ・項目の過剰化を確認する。

**作らないもの**

全SourceのCard化、複雑な承認、専用UI、Capture後の必須タグ付け、Card自動大量生成は作らない。

### M4 — Graph / Entra Minimum Integration

**目的**

Graph / EntraでSPOに対する最小の許可操作を実証し、失敗時も手動運用へ戻れる境界を確立する。

**対応要件**

- Requirement IDs: FR-INT-002〜003、14.1、17.3、TBD-005〜006
- Acceptance Criteria IDs: AC-M365-001、AC-M365-003、AC-SEC-001

**依存**

- 前提Milestone: M2、M3のSPO構成
- External dependency: Entraアプリ登録、管理者同意、Graph / SPO可用性

**設計判断**

- 委任 / アプリ権限は実行主体と最小権限で比較し、採用根拠をDecision Record化する。
- 最小実証はLibrary / Listの読み取りまたは限定書き込み1件で十分とし、同期基盤へ拡張しない。
- PnP等はGraphで満たせない具体的操作があり、MVP価値がある場合だけ比較する。

**Cursor実装範囲**

- 認証設定を環境変数へ分離した最小Graph smoke integration。
- 成功 / 失敗、必要権限、API制約をM365 Validation Logへ記録する仕組み。
- Graph無効時にローカル生成物と手動投入経路へ切り替わる確認。

**Human Action**

- アプリ登録、redirect / credential設定、必要な同意を最小範囲で行う。
- 取得できない権限は無理に拡張せず、管理上の阻害として記録する。

**検証**

- 許可済みreadまたはwriteを1件実行し、対象と結果を確認する。
- 無効credential、権限不足、SPO停止を想定した失敗でSecret漏えいとRaw損失がない。
- 手動SPO投入でM3運用が継続する。

**Exit Gate**

AC-M365-001を満たす成功証拠、または再現可能な阻害・必要権限・見送り判断があり、手動フォールバックが確認済みである。

**Codex Review Gate**

権限過大、テナント情報混入、Graphの必須依存化、PnPの無目的導入がないことを確認する。

**作らないもの**

双方向完全同期、汎用SPO provisioning、常駐daemon、複雑なPower Automateフローは作らない。

### M5 — Sensor Go / No-go and Licensing

**目的**

研究、技術者、企業、一般関心の4系統について、規約に適合し4か国・対象期間・時刻を観測できる候補を小規模検証する。

**対応要件**

- Requirement IDs: FR-DATA-001、FR-DATA-003、12.2〜12.5、17.2、TBD-001、TBD-003
- Acceptance Criteria IDs: AC-DATA-001、AC-DATA-003、AC-SEC-001

**依存**

- 前提Milestone: M1のログ / Raw骨格
- External dependency: 公開API / download、各利用規約

**設計判断**

- 各系統は候補比較表からgo / conditional go / no-goを決める。特定サービスを要件化しない。
- 4か国が不均衡でもRaw試行は止めず、欠落を品質情報として保持する。
- 再配布不可Rawは公開Repository外に置き、公開物は取得手順、メタデータ、合成 / 許可サンプルとする。
- Developer sensorはOrganization / Repository / aggregate-firstとし、個人User identityや個人LocationをPublic Repositoryへ保存しない。`unknown`削減を目的に個人情報の処理範囲を広げない。

**Cursor実装範囲**

- 各候補の少量smoke取得と、共通run manifestへの記録。
- country evidence、時刻種類、topic判定可能性、レート制限、取得期間のprofiling。
- ToS / license確認記録と採否表の作成。

**Human Action**

- 利用規約・ライセンスの境界が曖昧な候補をレビューし、無理なscrapingを許可しない。
- 個人User情報のローカル処理が不可避と判明した場合、保存範囲、保持期間、公開禁止、匿名化 / 集約可否をHuman + Codexで実装前に判断する。要件17.2に抵触する処理が必要なら実装せずRequirements Change Requestへ上げる。

**検証**

- 各系統でサンプル、4か国属性の可否、時刻、利用条件、fallbackが記録される。
- `unknown`を推測で埋めず、取得不能とゼロを区別する。

**Exit Gate**

4系統すべてに採用候補または根拠付きno-go / fallbackがあり、AC-DATA-001を満たす。加えてResearch Feasibility Gate RFが通過している。RF不成立時はM7の大規模backfillへ進まず、Research MUSTを`blocked`としてHumanへ返す。採用候補の本取得はGate Dまで開始しない。

**Codex Review Gate**

規約、再配布、国判定、期間coverage、API偏り、4か国が揃わない場合の主張制限を確認する。

**作らないもの**

SNS収集、規約が曖昧なscraper、全候補の完全Connector、LLMによるlocation補完は作らない。

### M6 — Methodology Gates and Data Contract Freeze

**目的**

Gate A〜Eを通過し、Rawから週次Canonicalと分析へ進むための意味・版・品質状態を固定する。

**対応要件**

- Requirement IDs: FR-DATA-006〜007、FR-ANL-001〜004、12.1、12.4〜12.7、15.1〜15.3、TBD-007〜010
- Acceptance Criteria IDs: AC-DATA-003〜005、AC-ANL-001〜002

**依存**

- 前提Milestone: M5の実サンプルとResearch Feasibility Gate RF通過。M3は独立経路でありM6の前提にしない
- External dependency: 4言語辞書のHuman review

**設計判断**

- Gate A：センサー別unit / population / denominator / weekly aggregation / normalization /比較範囲。
- Gate B：sensor、actor、social layer proxy、limitationsの分離。
- Gate C：event / publication / observed / ingestion timeとCanonical基準時刻。
- Gate D：2テーマ × 4言語辞書初版と除外条件。
- Gate E：一次属性、unknown、複数国Raw保持、国別集計規則。
- 採用指標と先行判定は実データ品質に基づき最小1組へ絞り、分析開始前に版を凍結する。

**Cursor実装範囲**

- Decision Record、辞書構成、rule version、データ契約の概念定義。
- 辞書サンプル照合支援と回帰fixture。
- zero / missing / unknown / fetch_failureを分ける品質状態の実装方針。
- RawからCanonicalへの変換仕様と検証fixture。完全DDLは作らず実装に必要な列だけを確定する。

**Human Action**

- 4言語辞書の境界事例とResearch Card項目を確認する。
- 先行指標の探索価値と、比較不能なセンサーの除外を承認する。

**検証**

- Gate A〜E checklistを全件レビューする。
- 曖昧語のfalse-positive sample、unknown比率、複数国の集計差を確認する。
- 異尺度の生値を同一グラフ・同一数値として比較しないことを仕様で確認する。

**Exit Gate**

2026-08-31までにGate A〜EのPass criteria、辞書版、集計rule版、品質状態、Canonical基準時刻が凍結され、未通過センサーはRawのみという境界が明確である。Codex Architecture Freeze Reviewの結果と09-01以後の停止条件がDecision Recordに残る。

**Codex Review Gate**

研究方法のadversarial reviewを行い、proxy混同、分母不在、publication lag誤認、unknown補完、仮説の事実化を検出する。

**作らないもの**

Gate未通過の分布指標、全センサー横断score、因果モデル、LLM主分類、社会階層の自動ラベルは作らない。

### M7 — Raw Ingestion and Historical Backfill

**目的**

採用した4系統候補について、2022-11-30から実行日までのRawを取得元粒度で保持し、失敗しても部分再実行できるようにする。

**対応要件**

- Requirement IDs: FR-DATA-002〜005、12.2〜12.6、16.1、19.1
- Acceptance Criteria IDs: AC-DATA-001〜005のRaw部分、AC-DATA-002

**依存**

- 前提Milestone: M1、M5（RF通過）、Gate D。国別集計はGate E後
- External dependency: 採用API / downloadの可用性、rate limit

**設計判断**

- Connectorはsource固有取得とRaw envelope生成に限定する。
- バックフィル区間、paging cursor、再試行、部分成功をrun manifestで追跡する。
- Raw payloadは利用条件に従い保存し、公開不可ならRepository外のlocal data rootへ置く。

**Cursor実装範囲**

- 採用候補のみの薄いConnector。
- 2022-11-30〜実行日のbounded backfillと、週次差分のwatermark基盤。
- 取得日時、対象期間、件数、失敗、API制約、概算コスト、データ版のログ。
- 重複識別、再試行、partial failure、source別停止を扱う。

**Human Action**

- 必要なAPI credentialを安全に設定し、規約上の取得範囲を最終確認する。

**検証**

- Connector smoke、paging、retry、idempotency、partial failureをテストする。
- Raw file checksum / manifest、期間coverage、重複、国evidence、時刻取得率をレポートする。
- 1センサーを停止して他センサーの処理が継続することを確認する。

**Exit Gate**

各採用センサーにRawとmanifestがあり、バックフィル対象期間・欠落・失敗を説明でき、同一Rawを上書きせず再実行できる。

**Codex Review Gate**

取得規約、Raw不変性、期間境界、欠落のゼロ化、過剰Connector抽象化、公開不可データ混入を確認する。

**作らないもの**

再配布不可Rawの公開、全API履歴の無制限取得、SNS Connector、完全自動schedulerは作らない。

### M8 — Weekly Canonical and Reproducible Analysis

**目的**

Rawを破壊せず週次Canonicalへ変換し、4か国 × 2テーマについて平均と少なくとも1つの分布形状または動態指標を再現可能に分析する。

**対応要件**

- Requirement IDs: FR-ANL-001〜004、12.6、15.1〜15.3、16.4〜16.5、19.3、TBD-009〜010
- Acceptance Criteria IDs: AC-DATA-003〜005、AC-ANL-001〜002

**依存**

- 前提Milestone: M6 Gate A〜E、M7 Raw
- External dependency: なし

**設計判断**

- 分析はセンサー内比較を第一とし、横断比較はGate Aで正規化可能と承認された指標だけに限定する。
- 先行の判定幅、閾値、採用指標は分析前にrule versionとして凍結する。探索で変更した場合は別版とする。
- FindingsはObservation / Quality & Limitations / Interpretation / Causal Hypothesesを分離する。

**Cursor実装範囲**

- version付きRaw → weekly Canonical変換。
- zero / missing / unknown / fetch_failureの保持、quality summary、country / theme / sensor別coverage。
- 平均と最小1指標の時系列分析、結果dataset、再現コマンド、静的図表または表。
- Current Findingsへ戻す公開可能artifact。

**Human Action**

- 予想外性、観測信頼性、価値を研究判断として評価し、原因の断定を行わない。

**検証**

- unit / transformation / reproducibility / dictionary regression / snapshot identity test。
- 同じRaw・辞書版・rule版からCanonicalと主要結果が再生成される。
- unknownとmissingを除外・包含した感度差を確認し、主張範囲を調整する。

**Exit Gate**

AC-ANL-001〜002を満たす再現分析と品質・限界があり、仮説不成立を含めてResearch Findingとして記録できる。

**Codex Review Gate**

異尺度比較、分母、時刻lag、multiple exploration、因果表現、再現性、指標の事後選択をadversarial reviewする。

**作らないもの**

統一指数、因果推論、株価予測、専用dashboard、必要性のない追加指標は作らない。

### M9 — BigQuery Parity Comparison

**目的**

M8で固定した同一または同等分析をBigQueryで最低1回実行し、DuckDBとの適合性・費用・運用差を期限前に比較する。

**対応要件**

- Requirement IDs: FR-ANL-005、14.3、18、19.3
- Acceptance Criteria IDs: AC-ANL-003、AC-PORT-001

**依存**

- 前提Milestone: M2 S6、M8の最小Canonical / query contract
- External dependency: BigQuery project、billing / Credit、network

**設計判断**

- 公開可能なCanonical subsetを用い、DuckDBと意味が同等な集計を選ぶ。
- 方言差で完全同一SQLが不合理な場合は、同一入力・同一定義・同一期待出力の同等queryとする。
- 性能はデータ量を併記し、小規模PoCでの絶対速度を一般化しない。

**Cursor実装範囲**

- 最小データ投入、比較query、結果差分検証、bytes processed / cost記録。
- 実装容易性、query互換性、性能、scale適応、cost、運用負荷、PoC適合性の比較文書。

**Human Action**

- GCP billing、Credit残高、dataset公開範囲を確認する。

**検証**

- 同一入力に対する主要集計が定義した許容差内で一致する。
- 実行日時、入力dataset identity、処理量、費用、環境差が記録される。

**Exit Gate**

2026-09-10までにAC-ANL-003を満たし、BigQueryを主基盤に移さず採否所見が`docs/cloud-comparison.md`にある。

**Codex Review Gate**

比較の同等性、費用根拠、データ量の過大一般化、GCP主基盤化がないことを確認する。

**作らないもの**

GCP AI処理、恒久warehouse移行、不要なCloud Storage pipelineは作らない。

### M10 — Weekly Operation, Selective Automation, and Optional Evaluation

**目的**

週次差分運用をローカルで安定させ、条件を満たす場合だけGitHub ActionsとAzure任意枝を検証する。

**対応要件**

- Requirement IDs: FR-DATA-002〜005、FR-INT-004〜006、10.3、14.2、16.1、18、TBD-011〜015
- Acceptance Criteria IDs: AC-DATA-002、AC-COST-001、AC-M365-003

**依存**

- 前提Milestone: M7、M8。AzureはM2 S7の採用判断
- External dependency: GitHub / Azureは採用時のみ

**設計判断**

- 自動化移行条件は、ローカル差分実行成功、idempotency、失敗復旧、secret分離、実行時間・費用の許容とする。
- Azure Blob / FoundryはResearch / Microsoft / Portfolio価値がコストを上回る場合だけ1件のbounded Spikeへ進む。
- Foundryは決定的処理を置換せず、AI出力を別artifactにする。

**Cursor実装範囲**

- 週次watermark、差分取得、snapshot比較、失敗後再実行の安定化。
- 条件通過時のみGitHub Actionsの最小workflowとsecret reference。
- 採用時のみBlob副本またはFoundry補助ユースケースの最小Spike、使用量 / 費用ログ。
- Researcher / Analyst / Power Automate等はHuman試行結果の記録支援のみ。

**Human Action**

- 初回backfill後の週次カレンダー窓と固定実行日をrunbookへ定め、2026-09-20を含む最終週のrunを09-17までに前倒しして実施する。少なくとも1回の差分実行と再開負荷を評価し、複数の週次窓が到来する場合は1回だけで完了扱いにしない。
- 任意機能の価値・費用を確認し、採用 / 不採用を判断する。

**検証**

- 差分更新が過去Rawを変更せず、重複せず、失敗を記録する。
- GitHub Actions採用時はSecretがログ / repositoryへ出ない。失敗時はローカル手動runが可能。
- Foundry採用時は1,000円以内、モデル / call / token / costが記録される。

**Exit Gate**

初回backfill後の各週次窓と、2026-09-20を含む最終週のrunが09-17までに実施・記録され、ローカル週次運用の再実行性が確認されている。自動化・Azure・追加M365機能ごとに採用 / 見送り理由がある。SHOULD / COULD未実施はMUST未達としない。

**Codex Review Gate**

自動化の早すぎる導入、Secret、課金、Azure任意性、外部障害時の継続性を確認する。

**作らないもの**

常時稼働基盤、複雑なorchestration、Foundry依存分析、目的のないMicrosoft機能網羅は作らない。

### M11 — Portfolio Completion and Three-axis Decision

**目的**

Milestoneごとの証拠をPublic Portfolioへ統合し、Research / Microsoft / Portfolioの三軸を受入基準で評価して継続判断する。

**対応要件**

- Requirement IDs: 4.1〜4.3、17.1〜17.3、18、19、21
- Acceptance Criteria IDs: AC-PORT-001、AC-SEC-001、AC-DEC-001、および全ACの最終確認

**依存**

- 前提Milestone: M1〜M10のMUST Exit Gate
- External dependency: Humanの最終判断、外部レビュー

**設計判断**

- Findingの強弱にかかわらず、実施条件、失敗、見送り、制約を残す。
- READMEから目的 → Architecture → Methodology → Validation → Findings → Cloud comparison → Decisionへ一方向にたどれる構成にする。
- 継続 / 縮小 / 見送りは三軸ごとに評価し、研究仮説不成立のみを終了理由にしない。

**Cursor実装範囲**

- 必須文書、公開サンプル、再現手順、license / attribution、結果artifactの整合。
- requirement / AC traceabilityの実績更新。
- Secret、テナント固有情報、個人情報、業務機密、再配布不可資料の公開前検査。

**Human Action**

- 2026-09-18までに三軸評価、M365 Trial継続、プロジェクト継続 / 縮小 / 見送りを決定する。
- Research Card Promoteと研究価値の最終判断を行う。

**検証**

- 全ACをpass / fail / blocked / not-applicableで記録し、証拠へのlinkを持たせる。
- クリーン環境または公開サンプルで主要分析手順を再実行する。
- 外部レビューで要件漏れ、因果表現、ライセンス、安全性を確認する。

**Exit Gate**

AC-PORT-001、AC-SEC-001、AC-DEC-001を満たし、未達MUSTがある場合は完了扱いにせず、阻害・影響・判断が明記されている。

**Codex Review Gate**

Section 21の6自己レビュー項目、Requirements Matrix、研究主張、公開安全、費用、期限、継続判断の証拠を最終確認する。

**作らないもの**

結果を良く見せるための事後的指標変更、未実施機能の完成扱い、専用Portfolio Siteは作らない。

## 7. Proposed Repository Logical Structure

```text
.
├─ README.md                         # 目的から判断までの公開入口
├─ AGENTS.md                         # SHOULD: Cursor / Codex共通の短い作業境界
├─ pyproject.toml                    # Python 3.12、依存・ツール設定
├─ uv.lock                           # 再現可能な依存固定
├─ .env.example                      # 値を持たない設定例
├─ config/
│  ├─ themes/                        # 2テーマ × 4言語の版管理辞書
│  ├─ sensors/                       # source別の非Secret設定
│  └─ rules/                         # aggregation / country ruleの版管理定義
├─ src/thought_flow/
│  ├─ ingestion/                     # 採用sourceの薄い取得AdapterとRaw envelope
│  ├─ normalization/                 # Raw → weekly Canonical、品質状態
│  ├─ analysis/                      # 版固定された指標と比較
│  ├─ integrations/
│  │  ├─ sharepoint/                 # Graph / SPO最小連携。手動経路と分離
│  │  ├─ bigquery/                   # 同一・同等分析の比較境界
│  │  └─ azure_optional/             # 採用時のみBlob / Foundry Spike
│  ├─ publishing/                    # 公開可能Findings / SPO投入物
│  ├─ observability/                 # run manifest、構造化ログ、費用
│  └─ config/                        # 設定読込とSecret境界
├─ data/
│  ├─ README.md                      # 公開・非公開、再配布、生成方法の境界
│  └─ samples/                       # 公開可能または合成された最小サンプル
├─ workspace-data/                   # Git管理外のlocal Raw / Canonical / result
│  ├─ raw/
│  ├─ canonical/
│  ├─ results/
│  └─ manifests/
├─ docs/
│  ├─ requirements.md                # 要件正本
│  ├─ architecture.md
│  ├─ methodology.md
│  ├─ m365-validation.md
│  ├─ research-findings.md
│  ├─ cloud-comparison.md
│  ├─ decisions/                     # TBD / Gateの短いDecision Record
│  └─ operations/                    # 手動実行、SPO設定、週次runbook
├─ tests/
│  ├─ unit/
│  ├─ transformations/
│  ├─ contracts/
│  ├─ connectors/
│  └─ fixtures/
└─ .github/workflows/                # M10で移行条件通過時のみ
```

`workspace-data/`は論理上の既定候補であり、実際のlocal data rootは設定で変更可能にする。公開RepositoryにはRaw本体を原則含めず、`data/samples/`に権利確認済みまたは合成した最小データだけを置く。`integrations/`に置いたコードをLocal Raw → Canonical → Analysisの必須import経路にしない。source数が少ない間は1 source = 1 module程度に留め、抽象継承階層を作らない。

## 8. Data Flow / Data Contracts

### 8.1 処理段階

| 段階 | 入力 | 出力 | 不変条件 |
|---|---|---|---|
| Acquire | source request条件 | source response + run evidence | 失敗もrunとして記録する |
| Raw persist | source response | immutable Raw record / file + manifest | 原粒度・原値を可能な限り保持し、上書きしない |
| Classify evidence | Raw | theme match evidence、country evidence、quality flags | LLM推測で補完しない |
| Canonicalize | Raw + dictionary / rule versions | weekly Canonical | Raw非破壊、基準時刻・分母・版が明確 |
| Analyze | Canonical + analysis rule version | result tables / figures / quality report | 異尺度生値を直接横断比較しない |
| Publish | results + human interpretation | public artifact / SPO Findings | 観測・限界・解釈・仮説を分離する |

### 8.2 Raw contractに必須の概念

完全SchemaはM6でsource sampleを見て決めるが、次の概念を欠落させない。

- `record_identity`：source内IDと、再取得・重複判定用の安定識別
- `raw_content_identity`：Raw内容のchecksumまたは同等の決定的識別。runが異なっても同一内容を判別する
- `source_identity`：sensor系統、具体source、endpoint / collectionの識別
- `raw_payload_or_reference`：利用規約に従う原値または非公開保存先参照
- `country_evidence`：明示されたaffiliation / location / headquarters / country filter等の一次属性と出所
- `theme_evidence`：一致語、辞書版、除外条件、判定状態
- `timestamps`：取得可能なevent / publication / observed / ingestion timeとtimezone / precision
- `retrieval_window`：要求した対象期間、paging / cursor、取得日時
- `measurement_payload`：source固有の値、件数、index等。source間で同尺度と見なさない
- `quality_state`：success、partial、missing attribute、fetch failure、重複候補等
- `usage_metadata`：利用条件確認日、保存 / 再配布区分
- `run_identity`：実行、コード版、設定版、費用記録へ結び付くID

### 8.3 Canonical contractに必須の概念

- `canonical_identity`：sensor、週、テーマ、国 / unknown、rule versionで一意となる識別
- `sensor`と`source`：社会階層ラベルとは分離する
- `population_and_denominator`：何を数え、何で正規化したか
- `country`：JP / US / KR / CN / unknown。複数国規則版とevidence集約を追跡する
- `theme`：Generative AI / AI Agentとdictionary version
- `canonical_time`：週境界、使用した時刻種別、timezone、既知のlag
- `measurement`：count / rate / index等の型とsource固有単位
- `quality_counts`：total、valid、unknown、missing、duplicate、failureの件数
- `coverage`：期待期間・期待母集団に対する観測可能範囲
- `source_snapshot_identity`：使用Raw manifest / checksumの集合
- `aggregation_rule_version`：分母、複数国、欠損、週次規則を再現する版

### 8.4 Analysis Result contractに必須の概念

- `analysis_identity`と実行日時
- 入力Canonical snapshot、辞書版、集計rule版、analysis rule版
- 対象sensor / source / country / theme / period
- 指標名、定義、単位、denominator、比較対象
- 推定値、必要なら不確実性・サンプル数・適用不能理由
- zero / missing / unknown / failureの扱いと感度所見
- observation、quality / limitations、interpretation、causal hypothesisの区分
- code revision、run ID、再実行入口、公開可否

### 8.5 品質状態の意味

| 状態 | 意味 | 集計規則 |
|---|---|---|
| zero | 成功した取得・観測窓で対象が0であることを確認 | 0として扱えるが、分母とcoverageが必要 |
| missing | 属性または測定値が提供されない / 適用できない | 0へ変換しない。理由別に保持 |
| unknown | 観測値はあるが国など対象属性を一次情報で判定できない | 正常なcategoryとして保持し比率を報告 |
| fetch_failure | 取得要求が失敗し、その窓を観測できなかった | 欠損または0へ変換せず、再試行対象にする |
| partial | paging / source coverageの一部だけ成功 | 成功範囲と未取得範囲を分け、完全系列と同等に扱わない |

## 9. Research Methodology Decisions

### 9.1 Plan段階で固定する事項

- 週次Canonicalを分析用時間粒度とするが、Rawの元粒度を保持する。
- 比較はセンサー内を第一とし、異なるsourceの生値を同じ尺度として扱わない。
- Sensorは社会階層のproxy候補であり、micro / meso / macroそのものではない。
- 時刻はevent / publication / observed / ingestionを分離し、source固有lagを伝播遅延と同一視しない。
- 国は一次属性だけで判定し、unknownを保持する。Raw収集は複数国集計規則の決定を待つ必要はない。
- テーマ主判定はGit管理された4言語辞書と決定的規則で行う。LLMは補助検証に限定する。
- 原因仮説は観測結果から分離し、Phase 2 MVPで因果を確定しない。

### 9.2 Gate Decision Table

| Gate / TBD | Decision input | Decision timing | Reviewer | Freeze point |
|---|---|---|---|---|
| Gate A / TBD-009 観測単位・指標 | M5サンプル、取得粒度、母集団、分母、coverage、欠損率 | M6前半 | `codex-design`, `codex-review` | Canonical変換と本指標実装の前 |
| Gate B / TBD-010 social layer proxy | sourceのactor / population、観測バイアス、文献上の妥当性 | M6 | `codex-review` + Human | Methodology初版公開前 |
| Gate C 時刻 | 4時刻の取得率、精度、timezone、既知の収録遅延 | M5〜M6 | `codex-design`, `codex-review` | weekly Canonical生成前 |
| Gate D / TBD-007 辞書 | 4言語語彙、曖昧語、positive / negative sample、人手照合 | M6 | Human, `codex-review` | M7本バックフィル前 |
| Gate E / TBD-008 国集計 | 一次属性coverage、unknown率、複数国例、候補規則の感度 | M5〜M6 | `codex-review` + Human | 国別Canonical生成前 |
| TBD-001 source採否 | ToS、API、4か国、期間、時刻、rate limit、費用 | M5 | `codex-review` + Human | sourceの本Connector実装前 |
| TBD-002 Card項目 | シード3件の把握時間、必須入力数、再利用価値 | M3 | Human, `codex-review` | M3 Exit Gate |
| TBD-003 file / link境界 | 再配布権、Copilot可視性、保存負荷 | M3 / M5 | Human, `codex-review` | Corpus運用確定前 |
| TBD-004 3状態表現 | SPO標準機能、操作数、Cardなし利用性 | M3 | Human, `codex-review` | M3 Exit Gate |
| TBD-005〜006 Graph / PnP | 最小権限、管理者同意、Graph不足、手動代替 | M2〜M4 | `codex-review` + Human | M4実装前 / 中止判断時 |
| TBD-011〜012 Azure | MUST進捗、予算、課金制御、実ユースケース価値 | M2で予備、M10前に最終 | Human, `codex-review` | 任意Spike開始前 |
| TBD-013 M365追加機能 | entitlement、Research Hubへの自然な用途、手作業削減 | M2〜M10 | Human, `codex-review` | 各機能の採否前 |
| TBD-014 Actions | local weekly成功、復旧、Secret、時間、費用 | M10 | `codex-review` | workflow実装前 |
| TBD-015 性能目標 | backfill量、local実測、週次量、反復時間 | M7後 | `codex-review` | M10安定化判定前 |
| TBD-016 継続 | 三軸結果、費用、実利用、Trial制約 | M11 | Human | 2026-09-18 |

### 9.3 研究判断の変更管理

辞書、国集計、基準時刻、分母、指標、閾値をfreeze後に変更する場合は、旧版を保持し、変更理由、影響範囲、再集計対象、Findingsへの影響をDecision Recordへ残す。探索結果を見て閾値を変更した分析は別versionとし、事前規則による結果と混同しない。

## 10. Microsoft 365 Implementation Strategy

### 10.1 初期構成と責務

| 要素 | 役割 | MVP境界 |
|---|---|---|
| Research Hub Site | 公開情報研究専用の分離境界 | 既存業務Siteと混在させない |
| Sources Library | Captureと原典 / 公開参照の主面 | Card作成、タグ、要約を必須にしない |
| Research Cards List等 | Usedかつ継続価値があるSourceの圧縮知識 | 全Source台帳にしない。項目はシード試行で削る |
| Home | 目的と最小導線 | 機能カタログ化しない |
| Methodology | 観測モデルと測定規則 | 詳細コード文書の代替にしない |
| Current Findings | 観測、品質、限界、解釈の還流 | 因果を断定しない |
| M365 Validation Log | 機能単位のTrial知見と採否 | Sourceごとに更新しない |

### 10.2 実装順序

1. HumanがSPOの利用可否と最小Site作成権限を確認する。
2. SourcesとPagesを手動で構成し、シード3文献をCaptureする。
3. CardなしでCopilotが使える範囲を確認する。
4. 実利用後、価値がある文献だけResearch CardへPromoteする。
5. Graph / Entraで最小readまたはwriteを試す。
6. Graph不成立時も手動投入を正式fallbackとして残す。
7. Power Automate等は、実測した手作業を減らし、操作・保守コストを上回る場合だけ採用する。
8. Researcher / Analyst等はTrialで実在・利用可能・有用であることを確認してから、機能単位で採否を記録する。

### 10.3 Copilot検証ケース

- CardなしSourceを固有語で検索できるか。
- シード資料間の比較を依頼した時、参照範囲と引用元を確認できるか。
- SourceとResearch Cardを横断した要約ができるか。
- 原典の確認が必要な点を人が追跡できるか。
- 権限外・索引未反映・対象形式非対応を、存在しない情報と誤認しないか。

Copilot回答の正しさを自動的に観測事実とせず、実施日、入力条件、対象Source、出力所見、引用 / 原典確認、制約を記録する。

### 10.4 Manual fallback

Graph、Power Automate、Copilotのいずれが使えなくても、(1)HumanによるSourcesへのCapture、(2)ローカルFindingsの手動Page反映、(3)Research Cardの選択的手動PromoteでResearch Hub運用を継続する。自動化を使わないこと自体は失敗ではなく、採否根拠を成果とする。

## 11. Sensor Strategy

| 系統 | Initial candidate | Data needed | Country attribution feasibility | Timestamp quality | Topic classification | ToS / licensing risk | Fallback | Go / no-go point |
|---|---|---|---|---|---|---|---|---|
| Research | OpenAlex、arXiv | publication / work、著者所属、公開日、topic text / metadata | affiliation countryが一次属性。複数所属・unknownを保持 | publication / deposit / ingestion相当の違いを確認 | title / abstract / metadataへの4言語辞書。coverage差を記録 | API rate、metadata再配布、abstract権利を確認 | 4か国属性と期間coverageが高い候補を主とし、他方は補助または見送り | M5サンプル後、M6 Gate前 |
| Developer | GitHub | Organization / Repository / aggregate-firstの活動、明示された組織location、time、topic text | Organization等の非個人一次属性を優先。User profileを使わなければ判定不能な場合はunknownとし、個人情報処理を自動拡大しない | created / pushed / event / observedの意味を分離 | repo metadata等へ辞書。単独`agent`を除外 | API token、rate、公開データ利用条件、個人identity / Locationの保存・公開禁止 | 公開集計またはOrganization単位に限定。個人単位が不可避なら実装前にHuman + Codex判断またはRequirements Change Request | M5でprivacy境界、country coverage、期間取得性を確認後 |
| Company | 求人、企業IR、公式発表 | company identity、本社国、publication、公開text / count | 公開された本社所在地のみ | announcement / filing / posting / observedの遅延が大きい可能性 | 公式textへの辞書。文書種類差を分離 | siteごとに大。無理なscrapingと再配布を禁止 | 公開API / bulk download / RSS / bounded manual sampleを比較。系統no-goも根拠化 | M5で規約と4か国coverageが成立した候補のみgo |
| General interest | Google Trends等 | country-filtered weekly interest、query、period | serviceのcountry filterを一次属性として使用 | window / sampling / observed timeを記録 | 辞書語ごとのquery設計。query間scaleを安易に結合しない | 非公式API、sampling、再現性、利用条件が主リスク | 許可されたexport / manual bounded acquisition、または代替公開series。取得不能はno-go記録 | M5でToS、週次履歴、4か国、再実行性を確認後 |

### 11.1 共通go条件

- 対象期間の全部または明示可能な範囲を取得できる。
- 4か国属性またはunknownを一次情報に基づき表現できる。
- Canonicalに使う時刻の意味を説明できる。
- テーマ辞書を決定的に適用でき、サンプル誤検出を評価できる。
- 取得、ローカル保存、分析、公開サンプルのライセンス境界が記録される。
- 個人identity / Locationを永続化・公開せず、unknown削減のために個人情報の利用範囲を広げない。個人単位処理が不可避ならgoとしない。
- rate / costが4週間のPoCに収まり、失敗時に他系統を停止させない。

4か国が完全に揃わない候補も`conditional go`としてRaw取得を許可するが、欠落を補完せず、4か国比較の結論範囲を制限する。4系統すべてが揃うまで他の作業を止めない。

## 12. Testing / Validation Strategy

| Test layer | 対象 | 最低検証 |
|---|---|---|
| Unit tests | 設定、時刻、週境界、country / theme rule、費用計算、状態分類 | 境界値、timezone、unknown、曖昧語、空入力、部分入力 |
| Contract tests | Connector → Raw、Raw → Canonical、Canonical → Result | 必須概念、版、identity、quality stateが欠落しない |
| Transformation tests | 週次集計、denominator、複数国、重複、欠損 | Raw非変更、期待値fixture、zero / missing / unknown / failure分離 |
| Reproducibility tests | snapshotからCanonical / Result再生成 | 同じRaw・辞書・rule・code revisionで主要結果が一致 |
| Dictionary regression | 2テーマ × 4言語のpositive / ambiguous / exclusion sample | 既知false positive再発防止、単独`agent`除外、版追跡 |
| Connector smoke | 採用sourceの認証、少量取得、paging、rate、failure | 外部状態に依存するため本体unit testと分離。録画fixture等は規約範囲で使用 |
| Data quality | duplicate、missing、unknown、failure、coverage、time precision | sensor / country / theme / week別の品質summary |
| Graph / SPO manual | Capture、Cardなし利用、Copilot、Promote、最小Graph操作 | 日付、条件、操作数、証拠、制約、fallback |
| BigQuery parity | 同一入力・定義のDuckDB / BigQuery | row / aggregate差、null semantics、date week、費用、処理量 |
| Security / publication | Secret、Tenant ID、個人情報、再配布不可資料、license | 作業treeとGit履歴を公開前に検査し、sample由来を確認 |
| Operational | backfill、差分、再試行、partial failure、resume | 過去Raw非変更、重複なし、失敗窓の可視化、手動fallback |

### 12.1 テスト実行ゲート

- Commit単位：fast unit / transformation / dictionary regression。
- Connector変更時：該当sourceのmock / fixture test。credentialがある環境だけsmoke。
- Milestone Exit：対応AC、data quality report、公開安全確認。
- M8 / M9：固定snapshotで完全再現とparity比較。
- M11：クリーン環境または公開サンプルからREADME手順を第三者視点で再実行。

外部サービスの不安定さをunit test失敗と混同しない。smokeのfailureはrun evidenceとして残し、外部停止でローカルtest suite全体を失敗させない。

## 13. Logging / Reproducibility Strategy

### 13.1 Run manifest

各実行は次の概念を1つのrun manifestで追跡する。

- run ID、run type（spike / backfill / incremental / rebuild / analysis / publish）
- start / end time、code revision、環境識別の公開安全な要約
- target period、source、sensor、country filter、theme dictionary version
- request数、取得row数、保存row数、重複数、失敗数、partial数
- API limitation、rate / retry、coverage、警告
- estimated / actual cost、model / token（AI使用時）、BigQuery bytes processed
- Raw manifest / checksum、Canonical snapshot ID、aggregation rule version、analysis rule version
- status、failure category、resume point、生成artifactの参照

### 13.2 ログ境界

- 構造化されたmachine-readable logと、人向けMilestone / Validation Logを分ける。
- token、API key、credential、不要なTenant / subscription / project固有値、個人情報をログへ出さない。
- API response本文を無条件にログ出力しない。Raw保存規約に従い、ログにはidentityと件数を残す。
- 失敗、missing、unknown、zeroを異なるcategoryとして集計する。

### 13.3 Dataset identity

各run manifestと`run_identity`は実行ごとに一意であり、同じ入力の再実行でも再利用しない。Rawはsource / acquisition date / run ID等で追記管理し、`record_identity`と`raw_content_identity` / checksumにより別run間の同一record・同一内容を判別する。Canonicalの`canonical_snapshot_identity`は入力Raw content identity集合、辞書版、国集計版、時刻規則版、変換code revisionから決定可能にし、別runでも同じ入力と規則なら同じdata result identityへ参照できる。Analysis ResultはCanonical snapshotとanalysis rule版を参照する。完全なhash方式と保持期間はM1 / M6で決めるが、同じ名前で内容を差し替えない。

### 13.4 手動証拠

SPO、Copilot、Graph、Trial、管理者同意、課金設定は、実施日、環境の匿名化識別、目的、操作、期待、結果、制約、証拠の安全な所在、採否を記録する。Screenshotを公開する場合はテナント名、個人名、URL、ID、通知などを確認する。

## 14. Cost / Deadline Control

### 14.1 Cost guardrails

| 対象 | Guardrail | Checkpoint |
|---|---|---|
| Azure AI Foundry | 初期累計1,000円。model、call、input / output token、概算費用を記録し、到達前に停止判断 | S7採否前、各run後、累計50% / 80%時 |
| Azure non-AI | 無料枠または設定済み予算内。Blobは副本のみ | S7、M10採用前 |
| GCP | $300 Credit期限2026-09-20。BigQuery以外へ拡張しない | S6、M9投入前 / 実行後 |
| M365 | Trial終了・継続判断を2026-09-18までに行う | S1、M3 / M4後、M11 |
| Public APIs | rate / quota / paid tierをrun manifestへ記録。有料化を自動承認しない | M5採否、各backfill / weekly run |

課金アラートがサービスまたは権限上利用できない場合、その事実を記録し、より小さいbounded run、manual stop、事前見積で代替する。

### 14.2 Deadline health

毎Milestone Exitで、残日数、未達MUST、外部依存、次の期限依存Gateを確認する。

| 状態 | 条件 | 対応 |
|---|---|---|
| Green | 内部期限内、次のMUSTに2日以上の余白 | Plan継続。COULDはまだ開始しない |
| Amber | 内部期限を1〜2日超過、または外部承認待ち | COULD停止、SHOULD縮小、手動fallbackでMUST経路を進める |
| Red | 09-10時点でM8 / M9未成立、またはM365必須試験未着手 | 全任意枝と追加指標を停止し、最小1分析・BigQuery・M365証拠・公開安全へ集中 |

### 14.3 削減しても残すもの

遅延時も、Raw非破壊、Gate A〜E、4系統採否記録、2テーマ × 4言語辞書、unknown品質、SPO / Copilot / Graph試験、最小再現分析、BigQuery比較、Secret / license検査、三軸判断は残す。削減対象は追加source、追加指標、追加Pages、高度自動化、Azure任意サービス、追加M365機能、UIである。

## 15. Portfolio-by-Construction

文書はM11で一括作成せず、次の更新契約で逐次反映する。

| Milestone | 更新先 | 追記する証拠 |
|---|---|---|
| M1 | `README.md`, `docs/architecture.md`, `.env.example` | 目的、local-first構成、実行入口、Secret境界、公開方針 |
| M2 | `docs/m365-validation.md`, `docs/cloud-comparison.md` | entitlement、権限、課金、access Spike結果 |
| M3 | `README.md`, `docs/m365-validation.md`, `docs/methodology.md` | Hub構成、Capture / Use / Promote、操作数、シード試行、Card決定 |
| M4 | `docs/architecture.md`, `docs/m365-validation.md` | Graph / Entra境界、権限、成功 / 失敗、手動fallback |
| M5 | `docs/methodology.md`, data source / license notes | sensor候補、ToS、coverage、採否、再配布境界 |
| M6 | `docs/methodology.md`, `docs/decisions/` | Gate A〜E、辞書、国・時刻・分母・proxy、freeze版 |
| M7 | README実行手順、methodology | backfill、manifest、coverage、品質、再取得方法 |
| M8 | `docs/research-findings.md`, `docs/methodology.md` | 指標、観測、品質、限界、解釈、仮説、再現手順 |
| M9 | `docs/cloud-comparison.md` | DuckDB / BigQuery 7観点、費用、parity結果、採否 |
| M10 | README運用手順、validation / comparison | weekly run、Actions採否、Azure / M365任意機能採否 |
| M11 | 全文書 | link整合、AC実績、三軸評価、継続 / 縮小 / 見送り |

各更新は「行ったこと」だけでなく、「できなかったこと」「制約」「見送り理由」を含める。Research Findingの弱さを隠すためにMicrosoft成果を水増しせず、三軸を別々に評価する。

## 16. Cursor Handoff Rules

### 16.1 共通実装ルール

Cursorへ渡す各taskは1 Milestoneまたは1つの独立Work Packageに限定し、冒頭に次を含める。

1. Source of Truth：`docs/requirements.md` 1.0と本Planの対象節
2. Scope：変更してよいdirectory / artifactと、変更しない領域
3. Requirement IDs / Acceptance Criteria IDs
4. 前提Gate、入力fixture、外部依存
5. 実装成果物、検証command、Exit Gate
6. Secret / data rights / logging上の禁止事項
7. 未確定事項と、Cursorが決めずに止めるdecision boundary

2026-08-31のArchitecture Freeze時に、この共通ルールと凍結済みDecision Recordへの導線を`AGENTS.md`へ短く反映する。09-01以後、Cursorは`AGENTS.md`を要件正本の代替にせず、常に`docs/requirements.md`と本Planを優先する。

### 16.2 Cursorが守る禁止事項

- 隣接Milestoneの先回り実装や不要なrefactorを行わない。
- TBD、辞書、複数国集計、指標、閾値、認証権限を根拠なく固定しない。
- Gate A〜E通過前に本分析を実装しない。
- Rawを更新 / 削除せず、失敗を0へ変換しない。
- 氏名、言語、LLMで国を補完しない。
- source間の生値を同尺度として比較しない。
- 外部連携をlocal pipelineの必須import / 実行経路にしない。
- 再配布権不明データ、credential、固有IDをfixture、log、commitへ含めない。
- 新しいWeb UI、汎用framework、Card大量生成、SNS収集を追加しない。

### 16.3 Cursorの停止条件

要件矛盾、利用規約不明、権限拡大が必要、課金上限超過のおそれ、Gate未決定、公開禁止情報の混入を検出した場合、推測で進めず、観測事実、影響、選択肢を記録してHuman / Codexへ返す。外部source 1件の障害だけなら、当該runをfailureとして他の独立作業を継続する。

### 16.4 Handoff完了形式

Cursorは、変更ファイル、満たしたRequirement / AC、実行したtest、未実行testと理由、data quality所見、Secret / license確認、残るTBD、次Milestoneへの入力を返す。完了主張はExit Gateの証拠に基づく。

## 17. Codex Double-check Strategy

2026-08-31までは、CodexがM1、M2の設計境界、M5、Research Feasibility Gate、M6 Gate A〜EとData Contractを優先レビューし、Architecture Freezeを行う。09-01以後はCodexをHard dependencyにしない。各Milestoneの同じReview Gateは、凍結済みPlan / Decision Record / `AGENTS.md`、自動テスト、Cursorのhandoff記録を入力としてHuman + ChatGPTが実施できる。Codexが利用可能な場合のみ追加Adversarial Reviewを行う。レビュー主体にかかわらず、実装diff、test結果、Decision Record、品質report、外部証拠を次の10観点で確認する。

| # | Review観点 | 問い |
|---:|---|---|
| 1 | Requirements compliance | 対応MUST / MUST NOTとSource of Truthを守ったか |
| 2 | Acceptance criteria | ACを観測可能な証拠で満たしたか。未実施をpassにしていないか |
| 3 | Scope creep | UI、抽象化、自動化、Source、Pagesを不必要に増やしていないか |
| 4 | Research validity | 仮説を事実化せず、探索と確証、観測と因果を分離したか |
| 5 | Data semantics | unit、population、denominator、時刻、zero / missing / unknown / failureが正しいか |
| 6 | Reproducibility | Raw、版、snapshot、code revision、run手順から再生成できるか |
| 7 | Security / secrets | credential、固有ID、個人情報、過大権限がないか |
| 8 | Licensing / publication | 保存・再配布・引用・sample公開が条件に適合するか |
| 9 | Cost | Azure 1,000円、GCP Credit、API quota、予算記録を守るか |
| 10 | Deadline impact | 内部期限、未達MUST、外部待ち、削減判断は適切か |

### 17.1 特別Adversarial Review

- M5：各センサーを採用したいバイアスを排し、規約・coverage・unknownをno-go側から評価する。
- M6：Gate A〜Eに対し、異尺度、生存者偏り、publication lag、proxy混同、辞書偏りを反例で確認する。
- M8：平均より先に動いたように見える結果が、欠損、母数変化、収録遅延、事後選択で説明できないか確認する。
- M9：BigQueryとDuckDBの同等性がSQL名ではなく入力・定義・出力で成立するか確認する。
- M11：公開成果からSecret / license問題を除き、弱い / null resultも追跡可能か確認する。

Review結果は`pass`、`pass with limitations`、`rework`、`blocked`のいずれかとし、`rework`は対象Milestone内で解消してから次の依存作業へ進む。09-01以後にCodexを利用できないこと自体は`blocked`理由にせず、未凍結の意味判断が必要な場合だけ該当作業を停止してHumanへ返す。

## 18. Risk Register Update

### 18.1 要件リスクをPlanで具体化したもの

| Risk | Plan上の具体化 | Trigger | Response |
|---|---|---|---|
| R-001 継続利用不能 | M3で1操作Capture、Cardなし利用、休止後再開を実測 | 必須入力増、Card作成待ち、再開時backlog要求 | 項目 / Page / 自動化を削り手動最小経路へ戻す |
| R-002 / R-003 M365 / 権限 | S1〜S3を08-28までに行いM3 / M4へ分離 | entitlementなし、同意不可、索引不可 | 制約を成果化し、SPO手動 / local publishへfallback |
| R-004 sensor取得 | M5でsourceごとにgo / no-go、規約、4か国coverage | 規約不明、履歴なし、地域粒度不足 | 代替候補、bounded manual、no-go記録。scrapingしない |
| R-005 / R-006 country / dictionary | Gate D / E、unknown比率、regression sample | unknown過多、曖昧語false positive | 結論範囲を狭め、辞書 / 規則を版更新しRawは保持 |
| R-007 異尺度 | Gate Aとsensor内比較優先 | 生値横断chart、分母なし指標 | 実装停止、contract / methodologyをrework |
| R-008 / R-009 null result / 因果 | M8結果構造とCodex adversarial review | 先行なし、原因表現、事後閾値 | null resultを公開し、観測 / 仮説を分離 |
| R-010 課金 | S7、1,000円、bounded Spike、run cost | 50% / 80%到達、見積不能 | 新規AI call停止、非AI経路へ戻す |
| R-011 期限 | 内部期限、M9を09-10、M11を09-18 | Amber / Red条件 | COULD→SHOULDの順で停止しMUSTへ集中 |
| R-012 公開安全 | M1 / M11 scanner、data boundary、履歴確認 | secret / ID / 不明license検出 | 公開停止、除外・credential rotation・履歴対応 |
| R-013 外部API | source別run、partial failure、manual resume | rate / schema / outage | 当該sensorのみ停止し他処理継続、影響期間を記録 |
| R-014 機能追加目的化 | 各Milestoneの「作らないもの」と削減順 | 新UI / framework / M365機能の追加 | 三軸価値と費用が示せなければno-go |

### 18.2 Planで新たに顕在化した実行リスク

以下は新しい製品要件ではなく、既存要件を実行する際の管理リスクである。

| ID | 実行リスク | 影響 | Mitigation |
|---|---|---|---|
| PR-001 | 4か国・4系統のcoverageが非対称で、AC-ANL-001の見た目だけを揃える圧力が生じる | 推測補完や無効な比較 | partial coverageを正式結果とし、国・sensor別の適用範囲を明示。最小分析は比較可能な単位を守る |
| PR-002 | Google Trends等の再取得でsampling値が変わる | snapshot再現差 | observed / ingestion time、query、window、snapshotを保持し、完全一致ではなくsource特性をLimitationsへ記録 |
| PR-003 | M365手動証拠のScreenshotに固有情報が映る | 公開漏えい | 公開用は匿名化したtext logを基本とし、画像はreview後のみ使用 |
| PR-004 | 4週間で複数の週次差分実行回数を確保しにくい | 安定性証拠が弱い | 初回backfill後の週次窓を固定し、09-20を含む最終週のrunを09-17までに実施。再実行 / watermark testで補完し、長期安定を過大主張しない |
| PR-005 | Research CardのAI生成を早期に試したくなる | 認知負荷とFoundry依存 | M3は手動最小Card、FoundryはM10採用時の1件Spikeだけに制限 |
| PR-006 | GitHubの公開User profileを個人情報でないと誤認する | 要件17.2違反、公開漏えい | Organization / Repository / aggregate-first、個人identity / Locationを永続化・公開しない。不可避なら実装停止とRequirements Change Request |
| PR-007 | 09-01以後もCodex Reviewを必須とみなす | 実装停止または未レビュー判断 | 08-31 Architecture Freeze、Decision Record、`AGENTS.md`、tests、Human + ChatGPT reviewへhandoff |

## 19. Requirement Traceability Matrix

要件節内の個別MUSTは、同一責務と検証経路を持つ単位で集約する。MUST NOTは対応する予防検証へ含める。再計数結果はFR 27件、AC 20件であり、下表のrange表記を展開して全IDの対応先を再照合済みである。

| Requirement / AC | Milestone | Validation |
|---|---|---|
| 4.1 Research成功条件 | M5 RF, M6, M7, M8, M11 | Feasibility Gate、Gate A〜E、4か国 × 2テーマの再現分析、null resultを含むFinding |
| 4.2 Microsoft成功条件 | M2, M3, M4, M11 | SPO動作、Copilotケース、Graph最小試行、Validation Log |
| 4.3 Portfolio成功条件 | M1〜M11 | 必須文書、再現手順、公開安全、三軸decision |
| 5.1 Research Hub / Corpus / 4 sensor / local基盤 / BigQuery | M1, M3, M5, M7〜M9 | Hub試験、sensor採否、Raw / Canonical、parity |
| 6 OUT OF SCOPE / MUST NOT | 全Milestone | Codex scope reviewと各「作らないもの」 |
| FR-HUB-001〜008 | M3 | AC-HUB-001〜005、シード3件、Source / Card / Findings導線 |
| FR-DATA-001 | M5 | AC-DATA-001、ToS / license / go-no-go表 |
| FR-DATA-002〜004 | M7, M10 | AC-DATA-002、backfill / incremental manifests |
| FR-DATA-005 | M1, M7, M10 | source停止test、local fallback |
| FR-DATA-006 | M5, M6, M8 | AC-DATA-003、unknown比率、禁止推測なし |
| FR-DATA-007 | M6, M8 | AC-DATA-004、辞書versionとresult追跡 |
| FR-ANL-001〜004 | M6, M8 | AC-DATA-005、AC-ANL-001〜002、再生成test |
| FR-ANL-005 | M2, M9 | AC-ANL-003、7観点とcostのparity report |
| FR-ANL-006 (SHOULD) | M8 | Current Findings投入artifactと手動反映 |
| FR-INT-001 | M2, M3 | AC-HUB-003、Copilot 4ケース |
| FR-INT-002 | M2, M4 | AC-M365-001、最小read / writeまたは阻害証拠 |
| FR-INT-003 (SHOULD) | M3, M4 | 手動投入fallback、local artifact保持 |
| FR-INT-004〜005 (COULD) | M2, M10 | 採否記録。採用時のみbounded Spike |
| FR-INT-006 (SHOULD) | M10 | 移行Gate、Secret参照、local fallback |
| 12.1〜12.3 観測軸・テーマ・国・期間・sensor | M5〜M8 | source profile、Gate A〜C、coverage / period report |
| 12.4 国判定 MUST / MUST NOT | M5, M6, M8 | Gate E、AC-DATA-003、evidence sample |
| 12.5 辞書 MUST / MUST NOT | M6, M7, M8 | Gate D、AC-DATA-004、regression test |
| 12.6 Raw / Canonical | M1, M6〜M8 | immutable Raw、weekly rebuild、quality states、AC-DATA-005 |
| 12.7 Research Card | M3 | 原典link、選択的Promote、最小項目Decision |
| 13.1〜13.3 Research Hub | M3 | 専用Site、公開情報限定、4 Pages、休止後再開 |
| 14.1 M365 | M2〜M4, M10 | entitlement、機能別Validation Log、採否 |
| 14.2 Azure | M2, M10 | optional採否、非依存test、採用時cost / AI separation |
| 14.3 GCP / BigQuery | M2, M9 | GCP非AI、最低1回parity、7観点比較 |
| 15.1〜15.3 研究姿勢・指標・仮説 | M6, M8 | Gate、version固定、観測 / 仮説分離、null result |
| 15.4 シード文献 | M3 | 3文献の通常運用試験、統一理論化しないreview |
| 16.1 可用性・疎結合 | M1, M4, M7, M10 | 外部連携off / source failure / manual fallback test |
| 16.2 利用性 | M3 | 1操作、必須入力、2週間再開、最小Pages / Card |
| 16.3 保守性・移植性 | M1, M7, M10 | config / secret分離、source isolation、Windows手順 |
| 16.4〜16.5 性能・品質 | M7, M8, M10 | backfill計測、品質summary、再実行一貫性 |
| 17.1 Repository / 成果物 | M1〜M11 | AC-PORT-001、README導線、必須artifact |
| 17.2 公開禁止 | M1, M5, M11 | AC-SEC-001、scanner、license / history review |
| 17.3 認証・権限 | M2, M4, M10 | 最小権限、`.env.example`、同意 / 制約ログ |
| 18 コスト | M2, M9〜M11 | AC-COST-001、Azure 1,000円、GCP期限、Trial decision |
| 19.1 取得・処理ログ | M1, M7, M10 | run manifest全項目、failure category |
| 19.2 M365 Validation Log | M2〜M4, M10 | 機能単位の7記録項目 |
| 19.3 分析再現性 | M5〜M9, M11 | sample / reacquisition、snapshot / versions、manual evidence |
| AC-HUB-001〜005 | M3 | 手動acceptance record |
| AC-M365-001〜003 | M2〜M4, M10 | external smoke、local fallback |
| AC-DATA-001〜005 | M5〜M8, M10 | source decision、manifests、quality / reproducibility tests |
| AC-ANL-001〜003 | M8, M9 | analysis rerun、Finding review、BigQuery parity |
| AC-COST-001 | M2, M10, M11 | Azure採否または1,000円以内のusage record |
| AC-PORT-001 / AC-SEC-001 / AC-DEC-001 | M1〜M11 | Portfolio audit、publication scan、three-axis decision |

## 20. Requirements Change Requests

None.

要件正本に、Plan作成時点で変更を要求する矛盾・実現不能・危険な点は確認していない。外部サービスの実利用可否、4センサーの具体source、複数国規則、指標等は、要件で許容されたTBDとして本PlanのSpike / Gateで決定する。

## 21. Final Self-Review

### A. Missing MUST

**PASS** — 要件節のMUST / MUST NOT、27件のFR、20件のACを再計数し、rangeを展開してMilestoneと検証へ対応付けた。未対応IDはない。外部機能が使えない場合も、要件で認められた検証記録とlocal fallbackを持つ。

### B. Overbuild

**PASS** — 11 Milestoneに限定し、Web UI、汎用Platform、Card大量生成、Knowledge Graph、SNS、過剰Connector抽象化を除外した。自動化はlocal weekly安定後、任意サービスは採否後だけである。

### C. Research validity

**PASS** — Gate A〜EをM6 Exit前提とし、sensor / social layer、異尺度、4種の時刻、unknown、辞書、分母を分離した。先行・因果は規則と品質が成立する範囲だけで述べる。

### D. Optional semantics

**PASS** — Azure Blob / FoundryはCOULDのまま、採否記録をMUST成果とした。不採用はPoC失敗ではない。

### E. Deadline

**PASS** — M5、Research Feasibility Gate、M6 Gate A〜E、Data Contract、Codex Architecture Freezeを08-31までに前倒しした。M8 / M9を09-10、09-20を含む最終週のrunを09-17、最終三軸評価を09-18に設定し、遅延時の削減順を定義した。

### F. Cursor usability

**PASS** — 各Milestoneに目的、対応要件、依存、設計判断、実装範囲、Human Action、検証、Exit Gate、Codex Review Gate、作らないものを記載し、Work Packageの共通handoff規則を定義した。

### Final assessment

本Planは`docs/requirements.md` 1.0の優先度とTBDを変更せず、CursorがM1から順に着手できる粒度と、勝手に決めてはならないGateを両立している。Research Feasibility、identity、privacy、Codex期限、FR / AC再計数をAdversarial Reviewで補正し、09-01以後もCodexを必須依存にしない運用を定義した。

**READY FOR PLAN FREEZE: YES**
