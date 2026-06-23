# Configuración de GWS para CV-Pilot

Esta guía te permite configurar Google Workspace CLI (`gws`) para que CV-Pilot pueda guardar borradores de correo en Gmail.

---

## 🛠️ Requisitos Previos

1. **Node.js 18+** instalado.
2. **gws CLI**:
   ```bash
   npm install -g @googleworkspace/cli
   ```
3. Una cuenta de Google (personal o de empresa) para usar **Google Cloud**.

---

## 🔐 Paso 1: Configuración de Google Cloud (GCP) y GWS

Para que CV-Pilot tenga permiso de crear borradores en tu Gmail, seguí estos pasos en la [Google Cloud Console](https://console.cloud.google.com/):

### 1.1. Crear proyecto de Google Cloud

Creá un proyecto de Google Cloud (sin organización, el nombre puede ser el que prefieras):

<img src="../images/gmail-setup/1.png" width="600" alt="Google Cloud Project 1">
<img src="../images/gmail-setup/2.png" width="400" alt="Google Cloud Project 2">

### 1.2. Habilitar Gmail API

En el menú lateral izquierdo de la consola de Google Cloud, seleccioná **APIs & Services**.

<img src="../images/gmail-setup/3.png" width="400" alt="APIs & Services">

Seleccioná el botón **+ Enable APIs and Services**.

<img src="../images/gmail-setup/4.png" width="400" alt="Enable APIs">

Buscá **Gmail API** y habilitála. Si no te aparece, seleccioná **Ver todo**.

<img src="../images/gmail-setup/5.png" width="400" alt="Gmail API">

Dentro de la API, hacé clic en **Habilitar** y esperá a que aparezca **✅ API Habilitada**.

### 1.3. OAuth Consent Screen

Una vez habilitada la API, configurá el consentimiento de OAuth. Hacé clic en **OAuth consent screen** en el menú lateral izquierdo.

<img src="../images/gmail-setup/6.png" width="400" alt="OAuth consent">

Seleccioná **Clients** en el menú lateral izquierdo y luego **+ Create Client**.

<img src="../images/gmail-setup/7.png" width="400" alt="Create Client">

Seleccioná **Desktop App** con el nombre que desees y presioná **Create**.

<img src="../images/gmail-setup/8.png" width="400" alt="Desktop App">

Te aparecerá un menú donde podés:
1. Copiar el **Client ID** y **Client Secret** (importante para configurar gws).
2. Descargar el JSON con las credenciales. Renombralo a **client_secret.json** y guardalo en un lugar seguro → **Esencial para el Paso 2**.

**Recomendación**: descargá el JSON con las credenciales aunque no hagas el Paso 2, así tenés tus credenciales guardadas.

<img src="../images/gmail-setup/9.png" width="400" alt="Credentials">

### 1.4. Configuración de gws

1. Con el client ID y client secret listos, ejecutá:

```bash
gws auth setup
```

2. Seleccioná tu cuenta de Google:

<img src="../images/gmail-setup/10.png" width="500" alt="Select account">

3. Seleccioná el proyecto que creaste (mismo nombre e ID del paso [1.1](#11-crear-proyecto-de-google-cloud)):

<img src="../images/gmail-setup/11.png" width="500" alt="Select project">

4. Seleccioná los servicios de API. Como mínimo necesitás **Gmail**:

<img src="../images/gmail-setup/12.png" width="500" alt="Select services">

5. Pegá el client ID y client secret del paso [1.3](#13-oauth-consent-screen):

<img src="../images/gmail-setup/13.png" width="500" alt="Client ID">
<img src="../images/gmail-setup/14.png" width="500" alt="Client Secret">

Cuando aparezca `Run gws auth login now? [Y/n]:` escribí `Y` y presioná Enter.

6. Te aparecerá una lista de scopes. Seleccioná **Recommended**. Para CV-Pilot, el scope mínimo necesario es `gmail.modify`.

<img src="../images/gmail-setup/15.png" width="700" alt="Scopes">

Copiá el link que aparece en la consola, abrilo en el navegador y otorgá los permisos a tu cuenta de Google. Al terminar verás:

<img src="../images/gmail-setup/16.png" width="700" alt="Success">

---

#### ⚠️ NOTA IMPORTANTE

El **Paso 2** es opcional. Si querés que tu sesión de gws permanezca abierta de forma permanente, hacelo. De lo contrario, tendrás que ejecutar `gws auth login` cada vez que enciendas el ordenador y vayas a usar CV-Pilot con Gmail.

---

## ⚙️ Paso 2: Persistencia de Sesión (Recomendado)

Para evitar que Google te pida login cada vez que reiniciás el PC:

### 2.1. En Windows, presioná `Win + R`, escribí `sysdm.cpl` y presioná Enter. Seleccioná **Advanced** → **Environment Variables**.

<img src="../images/gmail-setup/17.png" width="400" alt="System Properties">

### 2.2. Presioná **New** para crear una nueva variable de entorno.

<img src="../images/gmail-setup/18.png" width="400" alt="New variable">

### 2.3. Creá una variable de sistema llamada `GOOGLE_WORKSPACE_CLI_CONFIG_DIR` que apunte a una carpeta permanente con el nombre `.gws-config` (Ej: `C:\Users\TuUsuario\.gws-config`).

<img src="../images/gmail-setup/19.png" width="400" alt="Config dir">

### 2.4. Mové el archivo `client_secret.json` descargado en el paso [1.3](#13-oauth-consent-screen) dentro de esa carpeta `.gws-config`.

### 2.5. Una vez dentro de la carpeta `.gws-config`, volvé a ejecutar los pasos de [1.4](#14-configuración-de-gws):

```bash
gws auth login
```

---

## ✅ Verificación

Para comprobar que todo funciona, ejecutá:

```bash
gws auth status
```

Deberías ver `"token_valid": true` y `"gmail.modify"` en los scopes. Si es así, CV-Pilot ya puede guardar borradores en tu Gmail.

---

## ⚠️ Solución de Problemas

### Error 403: Insufficient authentication scopes
- **Causa**: No marcaste los permisos necesarios durante el login.
- **Solución**: Borrá el archivo `credentials.enc` en tu carpeta de configuración y repetí `gws auth login` seleccionando todos los permisos.

### gws: command not found
- **Causa**: gws no está instalado o no está en el PATH.
- **Solución**: Ejecutá `npm install -g @googleworkspace/cli` y reiniciá la terminal.

---

## 🔗 Referencias
- [Google Workspace CLI (gws)](https://github.com/googleworkspace/cli)
- [Gmail API](https://developers.google.com/workspace/gmail/api)
- [CV-Pilot Agent](https://github.com/Juliotamara23/CV-Pilot-Agent)
