-- W12 のマイグレーションの確認用: 初期状態（base.patch）のスキーマ version 4 とデータ。poc/scripts/grade_w12.py が SQLite のファイルに戻して使う
PRAGMA user_version = 4;
BEGIN TRANSACTION;
CREATE TABLE calibration_records (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        instrument_id  INTEGER NOT NULL REFERENCES instruments(id),
        calibrated_on  TEXT NOT NULL, -- YYYY-MM-DD
        result         TEXT NOT NULL CHECK (result IN ('pass', 'fail')),
        agency         TEXT NOT NULL, -- 校正機関
        certificate_no TEXT NOT NULL DEFAULT '',
        recorded_by    TEXT NOT NULL REFERENCES users(id),
        recorded_at    TEXT NOT NULL  -- ISO 8601（UTC）
      );
INSERT INTO "calibration_records" VALUES(1,1,'2026-01-20','pass','東日本計測サービス','EJ-26-00113','sato','2026-01-23T02:00:00.000Z');
INSERT INTO "calibration_records" VALUES(2,7,'2026-10-30','fail','東日本計測サービス','EJ-26-01876','kimura','2026-11-02T05:30:00.000Z');
INSERT INTO "calibration_records" VALUES(3,11,'2026-10-22','pass','東日本計測サービス','EJ-11','sato','2026-10-22T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(4,12,'2026-11-09','pass','東日本計測サービス','EJ-12','sato','2026-11-09T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(5,13,'2025-07-05','pass','東日本計測サービス','EJ-13','sato','2025-07-05T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(6,14,'2026-11-12','pass','東日本計測サービス','EJ-14','sato','2026-11-12T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(7,15,'2024-10-28','pass','東日本計測サービス','EJ-15','sato','2024-10-28T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(8,16,'2025-05-17','pass','東日本計測サービス','EJ-16','sato','2025-05-17T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(9,17,'2024-09-24','pass','東日本計測サービス','EJ-17','sato','2024-09-24T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(10,18,'2024-02-27','pass','東日本計測サービス','EJ-18','sato','2024-02-27T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(11,19,'2025-12-03','pass','東日本計測サービス','EJ-19','sato','2025-12-03T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(12,20,'2026-07-28','pass','東日本計測サービス','EJ-20','sato','2026-07-28T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(13,21,'2026-05-14','pass','東日本計測サービス','EJ-21','sato','2026-05-14T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(14,22,'2025-10-03','pass','東日本計測サービス','EJ-22','sato','2025-10-03T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(15,23,'2025-01-25','pass','東日本計測サービス','EJ-23','sato','2025-01-25T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(16,24,'2026-01-19','pass','東日本計測サービス','EJ-24','sato','2026-01-19T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(17,25,'2026-11-16','pass','東日本計測サービス','EJ-25','sato','2026-11-16T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(18,26,'2026-09-14','pass','東日本計測サービス','EJ-26','sato','2026-09-14T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(19,27,'2024-03-12','pass','東日本計測サービス','EJ-27','sato','2024-03-12T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(20,28,'2025-03-27','pass','東日本計測サービス','EJ-28','sato','2025-03-27T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(21,29,'2025-04-11','pass','東日本計測サービス','EJ-29','sato','2025-04-11T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(22,30,'2025-12-02','pass','東日本計測サービス','EJ-30','sato','2025-12-02T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(23,31,'2025-06-14','pass','東日本計測サービス','EJ-31','sato','2025-06-14T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(24,32,'2025-11-04','pass','東日本計測サービス','EJ-32','sato','2025-11-04T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(25,33,'2025-01-12','pass','東日本計測サービス','EJ-33','sato','2025-01-12T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(26,34,'2024-07-12','pass','東日本計測サービス','EJ-34','sato','2024-07-12T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(27,35,'2026-06-23','pass','東日本計測サービス','EJ-35','sato','2026-06-23T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(28,36,'2024-01-27','pass','東日本計測サービス','EJ-36','sato','2024-01-27T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(29,37,'2025-07-25','pass','東日本計測サービス','EJ-37','sato','2025-07-25T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(30,38,'2026-07-19','pass','東日本計測サービス','EJ-38','sato','2026-07-19T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(31,39,'2024-03-20','pass','東日本計測サービス','EJ-39','sato','2024-03-20T03:00:00.000Z');
INSERT INTO "calibration_records" VALUES(32,40,'2026-04-23','pass','東日本計測サービス','EJ-40','sato','2026-04-23T03:00:00.000Z');
CREATE TABLE departments (
        id                TEXT PRIMARY KEY,
        name              TEXT NOT NULL,
        representative_id TEXT -- 部署の代表者（users.id）
      );
INSERT INTO "departments" VALUES('qa','品質保証部','kimura');
INSERT INTO "departments" VALUES('mfg','製造部','yamada');
INSERT INTO "departments" VALUES('field','工事部','sasaki');
CREATE TABLE instruments (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        management_no      TEXT NOT NULL UNIQUE,
        name               TEXT NOT NULL,
        model              TEXT NOT NULL DEFAULT '',
        location           TEXT NOT NULL DEFAULT '',
        manager_id         TEXT NOT NULL REFERENCES users(id),
        interval_months    INTEGER NOT NULL CHECK (interval_months BETWEEN 1 AND 120),
        last_calibrated_on TEXT NOT NULL, -- YYYY-MM-DD
        status             TEXT NOT NULL DEFAULT 'in_use'
                           CHECK (status IN ('in_use', 'on_loan', 'calibrating', 'suspended', 'disposed')),
        note               TEXT NOT NULL DEFAULT ''
      );
INSERT INTO "instruments" VALUES(1,'MI-0001','デジタルマルチメータ','DMM-7510','品質保証部 測定室','sato',12,'2026-01-20','in_use','');
INSERT INTO "instruments" VALUES(2,'MI-0002','絶縁抵抗計','IR-4056','工事部 倉庫','tanaka',12,'2025-12-08','on_loan','');
INSERT INTO "instruments" VALUES(3,'MI-0003','トルクレンチ','TW-200N','製造部 第 1 ライン','suzuki',6,'2026-06-03','in_use','');
INSERT INTO "instruments" VALUES(4,'MI-0004','ノギス','CD-150AX','製造部 第 2 ライン','inoue',12,'2025-11-27','in_use','');
INSERT INTO "instruments" VALUES(5,'MI-0005','接地抵抗計','ER-4105','工事部 倉庫','tanaka',24,'2025-02-14','calibrating','');
INSERT INTO "instruments" VALUES(6,'MI-0006','クランプメータ','CM-2033','工事部 倉庫','yamamoto',12,'2026-03-11','in_use','');
INSERT INTO "instruments" VALUES(7,'MI-0007','マイクロメータ','MDC-25','品質保証部 測定室','kimura',12,'2025-10-30','suspended','');
INSERT INTO "instruments" VALUES(8,'MI-0008','検電器','HT-610','工事部 車両 3 号','kobayashi',12,'2024-08-01','disposed','');
INSERT INTO "instruments" VALUES(9,'MI-0009','オシロスコープ','DS-1054','品質保証部 測定室','takahashi',12,'2026-05-19','in_use','');
INSERT INTO "instruments" VALUES(10,'MI-0010','温湿度計','TR-72','製造部 恒温室','ito',12,'2025-12-25','in_use','');
INSERT INTO "instruments" VALUES(11,'MI-0011','ダイヤルゲージ','M-111','車両 2 号','inoue',24,'2026-10-22','in_use','');
INSERT INTO "instruments" VALUES(12,'MI-0012','デジタルマルチメータ','M-112','測定室','sato',6,'2026-11-09','disposed','');
INSERT INTO "instruments" VALUES(13,'MI-0013','絶縁抵抗計','M-113','倉庫','suzuki',12,'2025-07-05','suspended','');
INSERT INTO "instruments" VALUES(14,'MI-0014','トルクレンチ','M-114','第 1 ライン','tanaka',12,'2026-11-12','in_use','');
INSERT INTO "instruments" VALUES(15,'MI-0015','ノギス','M-115','車両 2 号','kimura',24,'2024-10-28','disposed','');
INSERT INTO "instruments" VALUES(16,'MI-0016','接地抵抗計','M-116','測定室','yamada',6,'2025-05-17','in_use','');
INSERT INTO "instruments" VALUES(17,'MI-0017','クランプメータ','M-117','倉庫','sasaki',12,'2024-09-24','suspended','');
INSERT INTO "instruments" VALUES(18,'MI-0018','マイクロメータ','M-118','第 1 ライン','takahashi',12,'2024-02-27','calibrating','前回は 2024-02-27 に外部校正（証明書あり）');
INSERT INTO "instruments" VALUES(19,'MI-0019','検電器','M-119','車両 2 号','ito',24,'2025-12-03','suspended','');
INSERT INTO "instruments" VALUES(20,'MI-0020','騒音計','M-120','測定室','watanabe',6,'2026-07-28','in_use','');
INSERT INTO "instruments" VALUES(21,'MI-0021','照度計','M-121','倉庫','yamamoto',12,'2026-05-14','disposed','');
INSERT INTO "instruments" VALUES(22,'MI-0022','圧力計','M-122','第 1 ライン','kondo',12,'2025-10-03','in_use','');
INSERT INTO "instruments" VALUES(23,'MI-0023','ダイヤルゲージ','M-123','車両 2 号','inoue',24,'2025-01-25','in_use','');
INSERT INTO "instruments" VALUES(24,'MI-0024','デジタルマルチメータ','M-124','測定室','sato',6,'2026-01-19','suspended','');
INSERT INTO "instruments" VALUES(25,'MI-0025','絶縁抵抗計','M-125','倉庫','suzuki',12,'2026-11-16','in_use','');
INSERT INTO "instruments" VALUES(26,'MI-0026','トルクレンチ','M-126','第 1 ライン','tanaka',12,'2026-09-14','in_use','');
INSERT INTO "instruments" VALUES(27,'MI-0027','ノギス','M-127','車両 2 号','kimura',24,'2024-03-12','in_use','前回は 2024-03-12 に外部校正（証明書あり）');
INSERT INTO "instruments" VALUES(28,'MI-0028','接地抵抗計','M-128','測定室','yamada',6,'2025-03-27','disposed','');
INSERT INTO "instruments" VALUES(29,'MI-0029','クランプメータ','M-129','倉庫','sasaki',12,'2025-04-11','calibrating','');
INSERT INTO "instruments" VALUES(30,'MI-0030','マイクロメータ','M-130','第 1 ライン','takahashi',12,'2025-12-02','on_loan','');
INSERT INTO "instruments" VALUES(31,'MI-0031','検電器','M-131','車両 2 号','ito',24,'2025-06-14','in_use','');
INSERT INTO "instruments" VALUES(32,'MI-0032','騒音計','M-132','測定室','watanabe',6,'2025-11-04','calibrating','');
INSERT INTO "instruments" VALUES(33,'MI-0033','照度計','M-133','倉庫','yamamoto',12,'2025-01-12','calibrating','');
INSERT INTO "instruments" VALUES(34,'MI-0034','圧力計','M-134','第 1 ライン','kondo',12,'2024-07-12','suspended','');
INSERT INTO "instruments" VALUES(35,'MI-0035','ダイヤルゲージ','M-135','車両 2 号','inoue',24,'2026-06-23','in_use','');
INSERT INTO "instruments" VALUES(36,'MI-0036','デジタルマルチメータ','M-136','測定室','sato',6,'2024-01-27','calibrating','前回は 2024-01-27 に外部校正（証明書あり）');
INSERT INTO "instruments" VALUES(37,'MI-0037','絶縁抵抗計','M-137','倉庫','suzuki',12,'2025-07-25','in_use','');
INSERT INTO "instruments" VALUES(38,'MI-0038','トルクレンチ','M-138','第 1 ライン','tanaka',12,'2026-07-19','in_use','');
INSERT INTO "instruments" VALUES(39,'MI-0039','ノギス','M-139','車両 2 号','kimura',24,'2024-03-20','in_use','');
INSERT INTO "instruments" VALUES(40,'MI-0040','接地抵抗計','M-140','測定室','yamada',6,'2026-04-23','disposed','');
INSERT INTO "instruments" VALUES(41,'MI-0041','クランプメータ','M-141','倉庫','sasaki',12,'2025-02-02','in_use','');
INSERT INTO "instruments" VALUES(42,'MI-0042','マイクロメータ','M-142','第 1 ライン','takahashi',12,'2025-08-22','disposed','');
INSERT INTO "instruments" VALUES(43,'MI-0043','検電器','M-143','車両 2 号','ito',24,'2024-10-24','disposed','');
INSERT INTO "instruments" VALUES(44,'MI-0044','騒音計','M-144','測定室','watanabe',6,'2026-01-21','in_use','');
INSERT INTO "instruments" VALUES(45,'MI-0045','照度計','M-145','倉庫','yamamoto',12,'2024-08-15','in_use','前回は 2024-08-15 に外部校正（証明書あり）');
INSERT INTO "instruments" VALUES(46,'MI-0046','圧力計','M-146','第 1 ライン','kondo',12,'2026-04-05','suspended','');
INSERT INTO "instruments" VALUES(47,'MI-0047','ダイヤルゲージ','M-147','車両 2 号','inoue',24,'2024-10-17','in_use','');
INSERT INTO "instruments" VALUES(48,'MI-0048','デジタルマルチメータ','M-148','測定室','sato',6,'2026-04-03','in_use','');
INSERT INTO "instruments" VALUES(49,'MI-0049','絶縁抵抗計','M-149','倉庫','suzuki',12,'2026-09-12','disposed','');
INSERT INTO "instruments" VALUES(50,'MI-0050','トルクレンチ','M-150','第 1 ライン','tanaka',12,'2026-11-11','suspended','');
INSERT INTO "instruments" VALUES(51,'MI-0051','ノギス','M-151','車両 2 号','kimura',24,'2026-08-14','in_use','');
INSERT INTO "instruments" VALUES(52,'MI-0052','接地抵抗計','M-152','測定室','yamada',6,'2025-09-02','in_use','');
INSERT INTO "instruments" VALUES(53,'MI-0053','クランプメータ','M-153','倉庫','sasaki',12,'2025-02-19','suspended','');
INSERT INTO "instruments" VALUES(54,'MI-0054','マイクロメータ','M-154','第 1 ライン','takahashi',12,'2025-08-23','disposed','前回は 2025-08-23 に外部校正（証明書あり）');
INSERT INTO "instruments" VALUES(55,'MI-0055','検電器','M-155','車両 2 号','ito',24,'2026-03-22','in_use','');
INSERT INTO "instruments" VALUES(56,'MI-0056','騒音計','M-156','測定室','watanabe',6,'2026-07-20','in_use','');
INSERT INTO "instruments" VALUES(57,'MI-0057','照度計','M-157','倉庫','yamamoto',12,'2026-05-20','calibrating','');
INSERT INTO "instruments" VALUES(58,'MI-0058','圧力計','M-158','第 1 ライン','kondo',12,'2026-07-07','in_use','');
INSERT INTO "instruments" VALUES(59,'MI-0059','ダイヤルゲージ','M-159','車両 2 号','inoue',24,'2025-12-06','in_use','');
INSERT INTO "instruments" VALUES(60,'MI-0060','デジタルマルチメータ','M-160','測定室','sato',6,'2026-08-07','in_use','');
CREATE TABLE loans (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        instrument_id INTEGER NOT NULL REFERENCES instruments(id),
        borrower_id   TEXT NOT NULL REFERENCES users(id),
        borrowed_at   TEXT NOT NULL, -- ISO 8601（UTC）
        due_on        TEXT NOT NULL, -- 返却予定日 YYYY-MM-DD
        returned_at   TEXT           -- ISO 8601（UTC）。未返却なら NULL
      );
INSERT INTO "loans" VALUES(1,2,'matsumoto','2026-11-02T00:15:00.000Z','2026-11-13',NULL);
INSERT INTO "loans" VALUES(2,6,'shimizu','2026-10-05T23:40:00.000Z','2026-10-09','2026-10-09T08:10:00.000Z');
INSERT INTO "loans" VALUES(3,11,'yamamoto','2026-09-01T00:00:00.000Z','2026-09-05','2026-09-05T09:00:00.000Z');
INSERT INTO "loans" VALUES(4,14,'yamamoto','2026-09-01T00:00:00.000Z','2026-09-05','2026-09-05T09:00:00.000Z');
INSERT INTO "loans" VALUES(5,16,'yamamoto','2026-09-01T00:00:00.000Z','2026-09-05','2026-09-05T09:00:00.000Z');
INSERT INTO "loans" VALUES(6,20,'yamamoto','2026-09-01T00:00:00.000Z','2026-09-05','2026-09-05T09:00:00.000Z');
INSERT INTO "loans" VALUES(7,22,'yamamoto','2026-09-01T00:00:00.000Z','2026-09-05','2026-09-05T09:00:00.000Z');
INSERT INTO "loans" VALUES(8,23,'yamamoto','2026-09-01T00:00:00.000Z','2026-09-05','2026-09-05T09:00:00.000Z');
INSERT INTO "loans" VALUES(9,25,'yamamoto','2026-09-01T00:00:00.000Z','2026-09-05','2026-09-05T09:00:00.000Z');
INSERT INTO "loans" VALUES(10,26,'yamamoto','2026-09-01T00:00:00.000Z','2026-09-05','2026-09-05T09:00:00.000Z');
INSERT INTO "loans" VALUES(11,30,'shimizu','2026-11-04T00:00:00.000Z','2026-11-30',NULL);
CREATE TABLE sessions (
        token      TEXT PRIMARY KEY,
        user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        expires_at TEXT NOT NULL -- ISO 8601（UTC）
      );
INSERT INTO "sessions" VALUES('old-session-token','sato','2026-11-12T00:00:00.000Z');
CREATE TABLE users (
        id            TEXT PRIMARY KEY,
        name          TEXT NOT NULL,
        department_id TEXT NOT NULL REFERENCES departments(id),
        active        INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)) -- 0 = 退職・休職など
      , password_hash TEXT NOT NULL DEFAULT '');
INSERT INTO "users" VALUES('sato','佐藤','qa',1,'scrypt$5cbb506cdb948a8257bab24cb5ef4c42$86008dedc5462431f65bf6f422a2fbb6e7577b8de36500bf1c70f8939aa56e01');
INSERT INTO "users" VALUES('suzuki','鈴木','mfg',1,'scrypt$5cbb506cdb948a8257bab24cb5ef4c42$86008dedc5462431f65bf6f422a2fbb6e7577b8de36500bf1c70f8939aa56e01');
INSERT INTO "users" VALUES('tanaka','田中','field',1,'scrypt$5cbb506cdb948a8257bab24cb5ef4c42$86008dedc5462431f65bf6f422a2fbb6e7577b8de36500bf1c70f8939aa56e01');
INSERT INTO "users" VALUES('kimura','木村','qa',1,'scrypt$5cbb506cdb948a8257bab24cb5ef4c42$86008dedc5462431f65bf6f422a2fbb6e7577b8de36500bf1c70f8939aa56e01');
INSERT INTO "users" VALUES('yamada','山田','mfg',1,'scrypt$5cbb506cdb948a8257bab24cb5ef4c42$86008dedc5462431f65bf6f422a2fbb6e7577b8de36500bf1c70f8939aa56e01');
INSERT INTO "users" VALUES('sasaki','佐々木','field',1,'scrypt$5cbb506cdb948a8257bab24cb5ef4c42$86008dedc5462431f65bf6f422a2fbb6e7577b8de36500bf1c70f8939aa56e01');
INSERT INTO "users" VALUES('takahashi','高橋','qa',1,'scrypt$5cbb506cdb948a8257bab24cb5ef4c42$86008dedc5462431f65bf6f422a2fbb6e7577b8de36500bf1c70f8939aa56e01');
INSERT INTO "users" VALUES('ito','伊藤','mfg',1,'scrypt$5cbb506cdb948a8257bab24cb5ef4c42$86008dedc5462431f65bf6f422a2fbb6e7577b8de36500bf1c70f8939aa56e01');
INSERT INTO "users" VALUES('watanabe','渡辺','mfg',1,'scrypt$5cbb506cdb948a8257bab24cb5ef4c42$86008dedc5462431f65bf6f422a2fbb6e7577b8de36500bf1c70f8939aa56e01');
INSERT INTO "users" VALUES('yamamoto','山本','field',1,'scrypt$5cbb506cdb948a8257bab24cb5ef4c42$86008dedc5462431f65bf6f422a2fbb6e7577b8de36500bf1c70f8939aa56e01');
INSERT INTO "users" VALUES('kobayashi','小林','field',1,'scrypt$5cbb506cdb948a8257bab24cb5ef4c42$86008dedc5462431f65bf6f422a2fbb6e7577b8de36500bf1c70f8939aa56e01');
INSERT INTO "users" VALUES('kato','加藤','qa',1,'scrypt$5cbb506cdb948a8257bab24cb5ef4c42$86008dedc5462431f65bf6f422a2fbb6e7577b8de36500bf1c70f8939aa56e01');
INSERT INTO "users" VALUES('yoshida','吉田','mfg',1,'scrypt$5cbb506cdb948a8257bab24cb5ef4c42$86008dedc5462431f65bf6f422a2fbb6e7577b8de36500bf1c70f8939aa56e01');
INSERT INTO "users" VALUES('matsumoto','松本','field',1,'scrypt$5cbb506cdb948a8257bab24cb5ef4c42$86008dedc5462431f65bf6f422a2fbb6e7577b8de36500bf1c70f8939aa56e01');
INSERT INTO "users" VALUES('hayashi','林','qa',1,'scrypt$5cbb506cdb948a8257bab24cb5ef4c42$86008dedc5462431f65bf6f422a2fbb6e7577b8de36500bf1c70f8939aa56e01');
INSERT INTO "users" VALUES('shimizu','清水','field',1,'scrypt$5cbb506cdb948a8257bab24cb5ef4c42$86008dedc5462431f65bf6f422a2fbb6e7577b8de36500bf1c70f8939aa56e01');
INSERT INTO "users" VALUES('inoue','井上','mfg',0,'scrypt$5cbb506cdb948a8257bab24cb5ef4c42$86008dedc5462431f65bf6f422a2fbb6e7577b8de36500bf1c70f8939aa56e01');
INSERT INTO "users" VALUES('kondo','近藤','field',0,'scrypt$5cbb506cdb948a8257bab24cb5ef4c42$86008dedc5462431f65bf6f422a2fbb6e7577b8de36500bf1c70f8939aa56e01');
CREATE INDEX users_department ON users(department_id);
CREATE INDEX sessions_user ON sessions(user_id);
CREATE INDEX instruments_manager ON instruments(manager_id);
CREATE INDEX loans_instrument ON loans(instrument_id);
CREATE INDEX calibration_records_instrument ON calibration_records(instrument_id);
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('instruments',60);
INSERT INTO "sqlite_sequence" VALUES('loans',11);
INSERT INTO "sqlite_sequence" VALUES('calibration_records',32);
COMMIT;
