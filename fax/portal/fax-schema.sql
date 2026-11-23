-- ════════════════════════════════════════════════════════════════════
--   📠 CimFAX 수신팩스 — 포털 DB 스키마 (MSSQL)
--   설계서 「CimFAX 수신팩스 포털 연동」 5.3 그대로 + fax_agent_status 추가.
--   ⚠ 포털 DB 가 MSSQL 이 아니면(예: MySQL) 타입을 바꿔 주세요:
--      BIGINT IDENTITY → BIGINT AUTO_INCREMENT,  DATETIME2 → DATETIME(3),
--      NVARCHAR→VARCHAR,  NVARCHAR(MAX)→TEXT,  BIT→TINYINT,  SYSDATETIME()→CURRENT_TIMESTAMP
--   partner_id 는 이관된 거래처(GURAE), voucher_id 는 수주·매입 전표를 가리킵니다(경영박사 설계서).
-- ════════════════════════════════════════════════════════════════════

CREATE TABLE fax_inbox (
  id              BIGINT IDENTITY PRIMARY KEY,
  received_at     DATETIME2      NOT NULL,
  sender_raw      NVARCHAR(64)   NULL,      -- CSID 원문
  sender_digits   VARCHAR(32)    NULL,      -- 숫자만
  mailbox         NVARCHAR(32)   NULL,      -- public, admin ...
  pages           SMALLINT       NULL,
  file_pdf        NVARCHAR(400)  NOT NULL,  -- 저장소 경로
  file_orig       NVARCHAR(400)  NULL,      -- 원본 TIF
  thumb           NVARCHAR(400)  NULL,
  sha256          CHAR(64)       NOT NULL UNIQUE,
  source          VARCHAR(20)    NOT NULL,  -- cimfax-export / cimfax-email / manual
  original_name   NVARCHAR(200)  NULL,
  partner_id      INT            NULL,      -- 거래처 (이관된 GURAE)
  match_type      VARCHAR(12)    NULL,      -- learned / exact / suggest / manual
  category        VARCHAR(20)    NULL,      -- order / quote / invoice / notice / spam / etc
  status          VARCHAR(12)    NOT NULL DEFAULT 'new', -- new / seen / done / archived
  assignee_id     INT            NULL,
  memo            NVARCHAR(1000) NULL,
  ocr_text        NVARCHAR(MAX)  NULL,
  created_at      DATETIME2      NOT NULL DEFAULT SYSDATETIME(),
  updated_at      DATETIME2      NULL
);
CREATE INDEX ix_fax_recv   ON fax_inbox(received_at DESC);
CREATE INDEX ix_fax_sender ON fax_inbox(sender_digits);
CREATE INDEX ix_fax_status ON fax_inbox(status, assignee_id);

CREATE TABLE fax_sender_map (            -- 번호→거래처 학습
  sender_digits   VARCHAR(32) PRIMARY KEY,
  partner_id      INT NOT NULL,
  updated_by      INT NULL,
  updated_at      DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);

CREATE TABLE fax_link (                  -- 팩스 ↔ 전표 (다대다)
  fax_id          BIGINT NOT NULL REFERENCES fax_inbox(id),
  voucher_id      BIGINT NOT NULL,       -- 수주·매입 전표
  PRIMARY KEY (fax_id, voucher_id)
);

CREATE TABLE fax_event (                 -- 열람·배정·상태 변경 이력
  id BIGINT IDENTITY PRIMARY KEY, fax_id BIGINT NOT NULL, user_id INT NULL,
  action VARCHAR(20) NOT NULL, detail NVARCHAR(400) NULL,
  at DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);

-- ── fax_agent_status (설계서 7.3 — 글로만 설명돼 있어 여기서 칸을 정함) ──
--   수집 에이전트(fax-agent)가 5분마다 /api/fax/agent-report 로 보낸 마지막 보고를 담는다.
--   agent 는 PC(에이전트)별 이름 — 에이전트가 여럿이면 여러 줄, 보통은 'default' 한 줄.
CREATE TABLE fax_agent_status (
  agent          VARCHAR(40)   NOT NULL PRIMARY KEY,  -- 에이전트/PC 이름(기본 'default')
  last_report_at DATETIME2     NULL,                  -- 마지막 보고 시각
  faxbox_running BIT           NULL,                  -- FaxBox 실행 여부
  total_in_db    INT           NULL,                  -- 점검 대상 수신 건수
  exported       INT           NULL,                  -- 폴더의 PDF 개수
  missing_count  INT           NULL,                  -- 누락(미저장) 건수
  missing_json   NVARCHAR(MAX) NULL,                  -- 누락 목록(JSON) — 팩스함 상단 경고에 쓴다
  updated_at     DATETIME2     NOT NULL DEFAULT SYSDATETIME()
);

-- ── (선택) 학습표 초기 채우기 안내 ──
--   설계서 5.2: 기존 FAXLIST 의 보낸번호 ~400개를 거래처 팩스번호와 한 번 맞춰
--   fax_sender_map 에 미리 넣어 두면 첫날부터 매칭률이 높습니다. (별도 1회 스크립트)
