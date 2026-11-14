# Kararsızım — Deployment

Canlı ortam: **Vercel** (proje `kararsizim`, bölge `fra1`) + **Supabase** Postgres (proje ref `blqgpmyvrankosvzxknj`, `eu-central-1`).
Kararların gerekçeleri: `docs/PROJECT.md` Bölüm 11 ve 15.

## Nasıl deploy olur

- Vercel projesi GitHub'daki `Oktay-Dadar/Kararsizim` reposuna bağlıdır. **`main`'e her push otomatik production deploy'dur.** Elle komut yok.
- Vercel `manage.py`'yi bulur, `config.settings` → `WSGI_APPLICATION` üzerinden giriş noktasını çıkarır. `STATIC_ROOT` tanımlı olduğu için `collectstatic` build sırasında kendiliğinden çalışır ve statik dosyalar Vercel CDN'den servis edilir. Sarmalayıcı dosya, rewrite veya build script'i **yoktur**.
- Python sürümü `.python-version` (3.14), bölge `vercel.json` (`fra1`, Supabase'e yakın). Pakete girmeyecek dosyalar `.vercelignore`'da.
- Migration'lar build'de **çalışmaz**; aşağıdaki gibi yerelden çalıştırılır. Model değişikliği içeren bir push'tan **önce** migration'ı uygula.

## Ortam değişkenleri (Vercel → Settings → Environment Variables, yalnızca **Production**)

| Değişken | Değer | Not |
|---|---|---|
| `DJANGO_SECRET_KEY` | rastgele, ≥50 karakter | Yerel `.env`'dekinden **farklı** |
| `VOTER_KEY_SALT` | rastgele | Değiştirilirse anonim ziyaretçiler aynı ankete yeniden oy verebilir — bir kez belirle, dokunma |
| `DATABASE_URL` | Supabase **transaction pooler** (port 6543) | `postgresql://postgres.blqgpmyvrankosvzxknj:<PAROLA>@aws-1-eu-central-1.pooler.supabase.com:6543/postgres` |
| `DJANGO_DEBUG` | `False` | |

`DJANGO_ALLOWED_HOSTS` ve `DJANGO_CSRF_TRUSTED_ORIGINS` gerekmez: settings, Vercel'in verdiği `VERCEL_PROJECT_PRODUCTION_URL`, `VERCEL_BRANCH_URL` ve `VERCEL_URL` adreslerini kendisi ekler. Özel alan adı bağlanırsa Vercel onu `VERCEL_PROJECT_PRODUCTION_URL` olarak verir; gerekirse ek adresler bu iki değişkene virgülle yazılır.

Anahtar üretmek (kendi terminalinde; çıktıyı sohbete yapıştırma):

```powershell
.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(50)); print(secrets.token_urlsafe(32))"
```

İlk satır `DJANGO_SECRET_KEY`, ikinci satır `VOTER_KEY_SALT`.

**Önemli:** Settings bu iki anahtarı import sırasında zorunlu okur ve Vercel build sırasında `manage.py`'yi çalıştırır. Değişkenler eksikse **build kırılır**. Değişken değiştirdikten sonra etkili olması için yeniden deploy gerekir (Deployments → son deploy → ⋯ → Redeploy).

Preview ortamına değişken girilmez: `main` dışındaki dallar build edilmeye çalışılırsa bilinçli olarak başarısız olur ve canlı veritabanına dokunamaz.

## Migration'ı yerelden çalıştırmak

Yerel `.env`'de `DATABASE_URL_DIRECT` (Supabase **session pooler**, port 5432) dolu olmalı. Transaction pooler'la migration patlar.

```powershell
$env:DJANGO_DB_DIRECT=1; .venv\Scripts\python manage.py migrate; Remove-Item Env:DJANGO_DB_DIRECT
```

Bash'te: `DJANGO_DB_DIRECT=1 .venv/Scripts/python manage.py migrate`

Yerel geliştirme ve production **aynı** Supabase veritabanını kullanır (prototip kararı). Yerelde `DATABASE_URL` doluyken yaptığın her şey canlıda görünür.

## Production'da yönetim

- Admin: `https://<canlı-adres>/admin/`. Superuser parolası güçlü olmalı; değiştirmek için yerelden (`.env` Supabase'e bağlıyken) `.venv\Scripts\python manage.py changepassword <kullanıcı>`.
- Loglar: Vercel → proje → **Logs**. `DEBUG=False`'ta hatalar stdout'a yazılır (settings'teki `LOGGING`).
- Geri alma: Vercel → **Deployments** → çalışan eski deploy → ⋯ → **Promote to Production** (Instant Rollback). Migration geri alınmaz; şema değiştiyse önce yerelden `migrate <app> <önceki_migration>`.

## Yerelde production ayarlarını denemek

```powershell
$env:DJANGO_DEBUG="False"; $env:DJANGO_SECURE_SSL_REDIRECT="False"
.venv\Scripts\python manage.py check --deploy
.venv\Scripts\python manage.py collectstatic --noinput
.venv\Scripts\python manage.py runserver
Remove-Item Env:DJANGO_DEBUG, Env:DJANGO_SECURE_SSL_REDIRECT
```

`check --deploy` için güçlü bir `DJANGO_SECRET_KEY` gerekir; yerel `.env`'deki zayıf anahtar `security.W009` uyarısı verir.

## Supabase güvenliği

- Data API kapalıdır (Supabase → Settings → API). Yedek önlem: `polls/migrations/0002_lock_down_supabase_api.py` (RLS açık, `anon`/`authenticated` yetkisiz).
- Doğrudan bağlantı (`db.<ref>.supabase.co`) yalnızca IPv6'dır; Vercel'den çalışmaz. Her zaman pooler adresi.
