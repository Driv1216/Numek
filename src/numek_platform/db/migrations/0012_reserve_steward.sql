-- S9: the reserve steward role holds ``reserve:consume`` (plan C.6, G.8): approval of restricted,
-- reserve-consuming investigations. Service principals can never hold it (enforced in code).
ALTER TABLE role_bindings DROP CONSTRAINT role_bindings_role_check;
ALTER TABLE role_bindings ADD CONSTRAINT role_bindings_role_check
    CHECK (role IN ('viewer', 'operator', 'analyst', 'approver', 'admin', 'reserve_steward'));
