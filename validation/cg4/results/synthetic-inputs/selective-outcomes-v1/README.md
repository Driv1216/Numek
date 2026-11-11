# Synthetic selective-label contract fixture

720 supplied prediction rows; explicit D/S/H are 240 each. Only correct H predictions
have final outcomes; each nonfinal status has 24 H observations. This is a product
and arithmetic example, not empirical statistical qualification or an independent
study. Unknown assumptions should refuse formal claims by default.

Load `InvestigationSpec.from_dict(spec, base_directory=fixture_directory)` in Python,
then inspect/discover. The tests in `tests/cg4/test_outcome_observation.py` exercise
observed-label versus complete-population inference using explicit synthetic-fixture
declarations. No customer data, encoder weights or predictor execution is involved.
