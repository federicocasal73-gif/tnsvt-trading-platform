-- Update admin@tnsvt.io to super_admin with new password
UPDATE platform.users
SET role = 'super_admin',
    password_hash = '$2b$12$2xTd8uAZ/FaDBIbk4w55ge9J.V8A.n9StKHjVGcTLtnD37DqVnyam',
    updated_at = NOW()
WHERE email = 'admin@tnsvt.io';

-- Delete all other users
DELETE FROM platform.users WHERE email != 'admin@tnsvt.io';

-- Delete all other tenants (keep only TNSVT id 814ca135)
DELETE FROM platform.tenants WHERE id != '814ca135-baf3-4007-9e25-d645374aaf77';

-- Verify
SELECT email, role, status FROM platform.users;
SELECT name, slug, status FROM platform.tenants;
