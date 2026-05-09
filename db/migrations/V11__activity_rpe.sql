-- RPE (Rate of Perceived Exertion) — subjektive Anstrengungseinschätzung 1–10
-- Ermöglicht Session-RPE-Load, Trainings-Monotonie, ACWR und HR:RPE-Effizienz
-- Quelle: Foster C et al. (2001) JSCR 15(1):109-115
ALTER TABLE activities
    ADD COLUMN user_rpe SMALLINT CHECK (user_rpe >= 1 AND user_rpe <= 10);
