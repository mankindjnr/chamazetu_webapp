UPDATE users
SET user_id = CASE
    WHEN id = 1 THEN '1'
    WHEN id = 2 THEN '2'
    WHEN id = 3 THEN '3'
    WHEN id = 4 THEN '12'
    WHEN id = 5 THEN '4'
    WHEN id = 6 THEN '5'
    WHEN id = 7 THEN '6'
    WHEN id = 8 THEN '7'
    when id = 9 THEN '8'
    WHEN id = 4700 THEN '9'
    WHEN id = 4701 THEN '10'
    WHEN id = 4702 THEN '11'
    ELSE user_id
END
WHERE id IN (1, 2, 3, 4, 5, 6, 7,8, 9, 4700, 4701, 4702);

-- turn the above case to single update statements
UPDATE users SET wallet_id = WCU4429 WHERE id = 1;
UPDATE users SET wallet_id = WBR2003 WHERE id = 2;
UPDATE users SET wallet_id = WHL4510 WHERE id = 3;
UPDATE users SET wallet_id = WMV6707 WHERE id = 4;
UPDATE users SET wallet_id = WQM3194 WHERE id = 5;
UPDATE users SET wallet_id = WDT9229 WHERE id = 6;
UPDATE users SET wallet_id = WDT9239 WHERE id = 7;
UPDATE users SET wallet_id = WWE6799 WHERE id = 4700;
UPDATE users SET wallet_id = WTU3097 WHERE id = 4701;
UPDATE users SET wallet_id = WDA466 WHERE id = 4702;