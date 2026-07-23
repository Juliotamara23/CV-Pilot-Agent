# Configuración de CLI for Microsoft 365 (m365) para CV-Pilot

Esta guía te permite configurar `m365` (CLI for Microsoft 365) para que CV-Pilot pueda guardar borradores de correo en Outlook a través de Microsoft Graph.

---

## 🛠️ Requisitos Previos

1. **Node.js 18+** instalado.
2. **CLI for Microsoft 365**:
   ```bash
   npm install -g @pnp/cli-microsoft365
   ```
3. Una cuenta de Microsoft con acceso a Outlook (personal `@outlook.com`, empresarial o educativa).

---

## 🔐 Paso 1: Crear App Registration en Azure

Para cuentas personales de Microsoft (`@outlook.com`, `@hotmail.com`), es obligatorio registrar tu propia aplicación. La app multi-tenant por defecto del CLI no soporta cuentas personales.

### 1.1. Acceder a Azure Portal

Ve a [Azure Portal > App Registrations](https://portal.azure.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade).

### 1.2. Crear la aplicación

1. **New registration** → nombre: `CV-Pilot`
2. **Supported account types**: **"Accounts in any organizational directory and personal Microsoft accounts"** ⚠️ Este paso es crítico. Si eliges otra opción, las cuentas personales no funcionarán.
3. **Redirect URI**: déjalo vacío por ahora, se configura después.
4. Haz clic en **Register**.

### 1.3. Configurar autenticación

1. En el menú lateral: **Authentication**
2. **Add a platform** → **Mobile and desktop applications**
3. Marcá `https://login.microsoftonline.com/common/oauth2/nativeclient`
4. **Configure**
5. Más abajo, en **Advanced settings** → **Allow public client flows**: **Yes**
6. **Save**

### 1.4. Agregar permisos de API

1. En el menú lateral: **API permissions**
2. **Add a permission** → **Microsoft Graph** → **Delegated permissions** ⚠️ Delegated, NO Application.
3. Busca y selecciona:
   - `Mail.ReadWrite`
   - `Mail.Send`
4. **Add permissions**

El consentimiento ocurre durante el login (no se necesita admin consent para cuentas personales).

### 1.5. Copiar el Client ID

Desde **Overview**, copia el **Application (client) ID**. Lo necesitarás para el login.

---

## 🔑 Paso 2: Iniciar sesión

### 2.1. Login con device code

```bash
m365 login --appId <TU_CLIENT_ID> --authType deviceCode --tenant consumers
```

⚠️ **Importante**: `--tenant consumers` es obligatorio para cuentas personales. Sin esto, el login falla con error de redirect URI.

Se mostrará un código. Ábrelo en `https://microsoft.com/devicelogin` y pégalo. Autoriza con tu cuenta de Microsoft.

### 2.2. Verificar sesión

```bash
m365 status
```

Deberías ver `"authType": "deviceCode"` y tu `appId`.

---

## ✅ Verificación

### 3.1. Probar conexión a Graph

```bash
m365 request --url "me" --method get
```

Si devuelve tu perfil, la autenticación es correcta.

### 3.2. Probar creación de borrador

**Paso A — Obtener token:**
```powershell
$token = m365 util accesstoken get --resource "https://graph.microsoft.com" --output text
```

**Paso B — Crear borrador:**
```powershell
$body = @{
  subject = "Prueba CV-Pilot"
  body = @{ contentType = "Text"; content = "Borrador de prueba generado por CV-Pilot." }
  toRecipients = @(@{ emailAddress = @{ address = "tucorreo@outlook.com" } })
} | ConvertTo-Json -Depth 3

$body | Out-File -FilePath "$env:TEMP\cvpilot_test.json" -Encoding utf8
$bodyJson = Get-Content -Path "$env:TEMP\cvpilot_test.json" -Raw -Encoding UTF8

Invoke-RestMethod -Uri "https://graph.microsoft.com/v1.0/me/messages" `
  -Method Post `
  -ContentType "application/json; charset=utf-8" `
  -Headers @{Authorization = "Bearer $token"} `
  -Body $bodyJson
```

Abrí Outlook (web o cliente) → carpeta **Borradores**. Debería aparecer el mensaje con `isDraft: true`.

---

## ⚠️ Solución de Problemas

### AADSTS50011: redirect URI does not match
- **Causa**: usaste `--authType browser` sin configurar `http://localhost` como redirect URI, o usaste `deviceCode` sin `--tenant consumers`.
- **Solución**: para cuentas personales, usá `m365 login --appId <ID> --authType deviceCode --tenant consumers`.

### ErrorAccessDenied al crear borrador
- **Causa**: los permisos `Mail.ReadWrite` no se agregaron como **Delegated** (se pusieron como Application).
- **Solución**: en API permissions, asegurate que los permisos sean Delegated, no Application. Luego `m365 logout` + `m365 login`.

### invalid_grant en device code
- **Causa**: la app no tiene "Allow public client flows" activado o le falta la plataforma Mobile/Desktop.
- **Solución**: en Authentication, verificá ambos settings (sección 1.3).

### Tildes y eñes rotas en el borrador
- **Causa**: `ConvertTo-Json` sin codificación UTF-8.
- **Solución**: escribir el JSON a archivo con `-Encoding utf8` y usar `-ContentType "application/json; charset=utf-8"`.

### m365: command not found
- **Solución**: `npm install -g @pnp/cli-microsoft365` y reiniciar la terminal.

---

## 🔗 Referencias

- [CLI for Microsoft 365](https://pnp.github.io/cli-microsoft365/)
- [Microsoft Graph: create message](https://learn.microsoft.com/graph/api/user-post-messages)
- [CV-Pilot Agent](https://github.com/Juliotamara23/CV-Pilot-Agent)
