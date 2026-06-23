# Configuración de CLI for Microsoft 365 (m365) para CV-Pilot

Esta guía te permite configurar `m365` (CLI for Microsoft 365) para que CV-Pilot pueda guardar borradores de correo en Outlook a través de Microsoft Graph.

---

## 🛠️ Requisitos Previos

1. **Node.js 18+** instalado.
2. **CLI for Microsoft 365**:
   ```bash
   npm install -g @pnp/cli-microsoft365
   ```
3. Una cuenta de Microsoft (personal, de empresa o educativa) con acceso a Outlook.

---

## 🔐 Paso 1: Instalación y Login

### 1.1. Verificar instalación

```bash
m365 --version
```

Si el comando no se reconoce, ejecuta:

```bash
npm install -g @pnp/cli-microsoft365
```

Reinicia la terminal y vuelve a probar. Si persiste, verifica que el directorio global de `npm` esté en el `PATH`.

### 1.2. Iniciar sesión

`m365` usa el flujo **device code** por defecto, ideal para entornos locales:

```bash
m365 login
```

Se mostrará un código en la terminal y una URL (`https://microsoft.com/devicelogin`). Ábrela en el navegador, pega el código y autoriza con tu cuenta de Microsoft.

Para una cuenta personal (sin tenant empresarial), el flujo device code funciona igual. Para tenants empresariales, tu administrador podría requerir consentimiento previo de la aplicación.

### 1.3. (Recomendado) Registrar tu propia app en Azure

El CLI puede usar su app predeterminada, pero registrar la propia ofrece ventajas:
- Control sobre los permisos (scopes) solicitados.
- Evita conflictos si otros usuarios comparten la misma máquina.
- Auditoría independiente en el tenant.

Pasos en [Azure Portal](https://portal.azure.com/):

1. **Microsoft Entra ID** → **App registrations** → **New registration**.
2. Tipo de cuenta: **Personal Microsoft accounts and accounts in any organizational directory** (o el alcance que aplique).
3. Redirect URI: **Public client/native** → `https://login.microsoftonline.com/common/oauth2/nativeclient`.
4. En **API permissions**, agrega **Microsoft Graph** → **Delegated**:
   - `Mail.ReadWrite`
   - `Mail.Send`
5. Copia el **Application (client) ID**.

Luego configura m365 para usar tu app:

```bash
m365 login --appId <TU_CLIENT_ID> --tenant common
```

### 1.4. Persistencia de sesión

`m365` guarda las credenciales en `~/.environments/` (multiplataforma). En la mayoría de los casos la sesión persiste entre reinicios. Si tu tenant exige reautenticación frecuente, revisa la política de tokens con tu administrador.

---

## ✅ Verificación

Comprueba el estado de la sesión:

```bash
m365 status
```

Deberías ver tu cuenta, el tenant y los scopes concedidos. Confirmación adicional:

```bash
m365 request --url "me" --method GET
```

Si devuelve tu perfil de usuario, la autenticación y los permisos son válidos.

---

## 🧪 Prueba de borrador

Crea un borrador de prueba en Outlook:

```bash
m365 request --url "me/messages" --method POST --body "{\"subject\":\"Prueba CV-Pilot\",\"body\":{\"contentType\":\"Text\",\"content\":\"Borrador de prueba\"},\"toRecipients\":[{\"emailAddress\":{\"address\":\"<tu_correo>\"}}]}"
```

Abre Outlook (web o cliente) → carpeta **Borradores** (Drafts). Debería aparecer el mensaje sin enviar.

---

## ⚠️ Solución de Problemas

### `m365: command not found`
- **Causa**: el paquete no se instaló o el directorio global de npm no está en el `PATH`.
- **Solución**: ejecuta `npm install -g @pnp/cli-microsoft365` y reinicia la terminal. Verifica con `npm root -g`.

### Error de consentimiento / permisos insuficientes
- **Causa**: el tenant exige consentimiento de administrador para los scopes `Mail.ReadWrite` o `Mail.Send`.
- **Solución**: registra tu propia app (Paso 1.3) o solicita al administrador que pre-consienta. Alternativamente, usa una cuenta personal.

### El borrador no aparece en Borradores
- **Causa**: la cuenta autenticada no tiene buzón activo, o el POST cayó en otro folder.
- **Solución**: verifica con `m365 request --url "me/mailFolders"` que la carpeta **Drafts** existe. Confirma que la sesión corresponde al buzón esperado con `m365 request --url "me"`.

### Código de device expira antes de autorizar
- **Causa**: tardaste más de 15 minutos en abrir la URL.
- **Solución**: vuelve a ejecutar `m365 login` para obtener un código nuevo.

### `m365 request` devuelve 401 Unauthorized
- **Causa**: el token expiró o los scopes del login no incluyen `Mail.ReadWrite`.
- **Solución**: ejecuta `m365 logout` y vuelve a hacer `m365 login`, asegurando los scopes necesarios.

---

## 🔗 Referencias

- [CLI for Microsoft 365 (PnP)](https://pnp.github.io/cli-microsoft365/)
- [Microsoft Graph: create message](https://learn.microsoft.com/graph/api/user-post-messages)
- [CV-Pilot Agent](https://github.com/Juliotamara23/CV-Pilot-Agent)