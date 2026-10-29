ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS age INTEGER;

ALTER TABLE public.profiles
    DROP CONSTRAINT IF EXISTS profiles_age_check;

ALTER TABLE public.profiles
    ADD CONSTRAINT profiles_age_check CHECK (age BETWEEN 10 AND 120);

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    raw_age JSONB;
    parsed_age NUMERIC;
BEGIN
    raw_age := NEW.raw_user_meta_data -> 'age';

    IF raw_age IS NULL OR jsonb_typeof(raw_age) <> 'number' THEN
        RAISE EXCEPTION 'Age must be a whole number between 10 and 120.'
            USING ERRCODE = 'check_violation';
    END IF;

    parsed_age := (raw_age #>> '{}')::NUMERIC;
    IF parsed_age <> TRUNC(parsed_age) OR parsed_age < 10 OR parsed_age > 120 THEN
        RAISE EXCEPTION 'Age must be a whole number between 10 and 120.'
            USING ERRCODE = 'check_violation';
    END IF;

    INSERT INTO public.profiles (id, email, full_name, age)
    VALUES (
        NEW.id,
        NEW.email,
        COALESCE(NEW.raw_user_meta_data->>'full_name', ''),
        parsed_age::INTEGER
    )
    ON CONFLICT (id) DO UPDATE SET
        full_name = EXCLUDED.full_name,
        age = EXCLUDED.age,
        updated_at = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.handle_new_user();
