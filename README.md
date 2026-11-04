# MPR - Integración multiproveedor

Este laboratorio integra AWS y Google Cloud mediante una aplicación que recibe una fotografía, la conserva en Amazon S3 y obtiene etiquetas que describen su contenido. Para este flujo se utilizará Cloud Vision y Amazon Rekognition, para poder comparar y adaptar los contratos tanto de entrada como de salida y luego poder comparar los resultados de dos servicios que, en teoría, son equivalentes.

El procesamiento es sincrónico y secuencial: el cliente envía la imagen y recibe los resultados en la misma llamada HTTP. Lambda espera la respuesta de Vision antes de solicitar el análisis de Rekognition.

La actividad se realiza desde AWS Management Console y Google Cloud Console, con las interfaces en inglés, y utiliza un cliente Python para enviar las imágenes. Una plantilla CloudFormation crea la infraestructura base. El código inicial se carga mediante un archivo ZIP proporcionado y los ejercicios se completan directamente en el editor de Lambda.

## Resultados esperados

Al completar el laboratorio el estudiante podrá:

1. Recibir una imagen mediante una Function URL y conservarla en S3
2. Implementar una solicitud HTTP a Cloud Vision, incluyendo autenticación, codificación de la imagen y lectura de la respuesta
3. Distinguir el execution role de AWS de la autenticación requerida por el proveedor externo
4. Analizar los mismos bytes mediante Cloud Vision y Amazon Rekognition, conservando sus respuestas originales
5. Adaptar nombres y puntajes de ambos contratos a una representación común
6. Comparar etiquetas mediante igualdad de nombres normalizados
7. Interpretar diferencias entre los resultados

## Preparación previa

Antes del laboratorio:

- Confirme que la cuenta AWS personal y su identidad administrativa de uso regular estén operativas y permitan crear los recursos de la actividad: CloudFormation, IAM, Lambda, S3 y CloudWatch Logs, además de utilizar Rekognition
- Disponga de acceso a un proyecto Google Cloud con **billing activo**
- Disponga de Python 3 en el computador desde el que enviará las imágenes
- Prepare una fotografía o más fotografías de práctica, JPEG o PNG de hasta **4 MiB**. Prefiera fotografías con objetos reconocibles y buena iluminación.
- Descargue [`infrastructure.yaml`](infrastructure.yaml), el paquete preparado [`lambda.zip`](lambda.zip) y [`client.py`](client.py)

El cliente utiliza solamente la biblioteca estándar de Python 3. No se necesita AWS CLI ni instalar bibliotecas adicionales.

### Consumo de los servicios

Cloud Vision permite analizar las primeras **1.000 unidades mensuales de Label Detection sin costo**, pero exige billing habilitado. Una característica aplicada a una imagen constituye una unidad; analizar otra vez la misma imagen vuelve a consumir el servicio.

AWS Rekognition está disponible con créditos en los planes **Free y Paid**. El cupo de imágenes gratuitas depende de cada cuenta. En este laboratorio también intervienen Lambda, S3, CloudWatch Logs y transferencia de datos.

## Contexto

Un catálogo de fotografías puede utilizar etiquetas para facilitar búsquedas sin que una persona describa manualmente cada imagen. Dos servicios pueden analizar la misma fotografía y producir nombres, niveles de detalle y puntajes distintos. Para relacionar sus resultados, primero es necesario interpretar ambos contratos.

El sistema utiliza una sola Lambda function y avanza por cuatro etapas:

| Etapa | Resultado |
| --- | --- |
| `upload` | Guardar la imagen en S3 y confirmar su recepción |
| `vision` | Consultar Cloud Vision y devolver sus etiquetas |
| `rekognition` | Incorporar Rekognition al análisis de Vision ya implementado y conservar ambas respuestas originales |
| `compare` | Adaptar los contratos y comparar etiquetas comunes y exclusivas |

S3 conserva la imagen y las respuestas originales de los análisis; no inicia el procesamiento. Lambda utiliza los mismos bytes recibidos en ambos servicios. Se emplean los modelos proporcionados por `LABEL_DETECTION` y `DetectLabels`; no se requiere entrenar modelos ni publicar los objetos S3.

`LAB_STAGE` determina hasta qué punto avanza la función de procesamiento y qué devuelve. En cada etapa se conservan las operaciones anteriores: `vision` agrega el resultado de Google a la imagen guardada; `rekognition` agrega la llamada a AWS después de Vision; `compare` agrega la comparación.

La integración con Vision permite comprobar la comunicación entre AWS y Google Cloud. Para completar el laboratorio, incorpore ambos análisis, conserve sus respuestas originales, adapte los contratos, compare las etiquetas e interprete sus puntajes de confianza.

## Materiales

| Archivo | Descripción |
| --- | --- |
| [`infrastructure.yaml`](infrastructure.yaml) | Plantilla CloudFormation de la infraestructura base |
| [`lambda.zip`](lambda.zip) | Paquete ZIP con el código inicial de Lambda |
| [`client.py`](client.py) | Cliente Python para enviar una imagen y mostrar la respuesta JSON |
| [`lambda/stages.py`](lambda/stages.py) | Cinco funciones de integración y comparación incluidas en el ZIP |
| [`lambda/lambda_function.py`](lambda/lambda_function.py) | Código de recepción HTTP, almacenamiento y coordinación |
| [`lambda/normalization.py`](lambda/normalization.py) | Funciones auxiliares de normalización y comparación |

La carpeta [`lambda/`](lambda/) contiene el mismo código expandido para consulta. El archivo `lambda.zip` es el paquete utilizado durante el laboratorio.

## Actividad

### 1. Recibir y conservar una imagen

#### 1.1 Crear el stack desde la consola

1. Ingrese a AWS Management Console con la identidad administrativa de uso regular
2. Seleccione **US East (N. Virginia)** y compruebe que la Región sea `us-east-1`
3. Abra **CloudFormation → Stacks → Create stack → With new resources (standard)**
4. Seleccione **Choose an existing template** y **Upload a template file**
5. Cargue `infrastructure.yaml` y avance con **Next**
6. Utilice `tel351-mpr` como **Stack name**
7. Mantenga las demás opciones por omisión y revise el resumen
8. Confirme en **Capabilities** la autorización para crear recursos IAM e inicie el despliegue con **Submit**
9. Espere hasta que el stack indique **CREATE_COMPLETE**

Mientras se despliega, lea el apartado siguiente. Si falla, revise **Events** e identifique el recurso y la causa informada antes de continuar. Al llegar a `CREATE_COMPLETE`, la función lambda creada solo contiene el código inicial de preparación y responde HTTP `503`.

#### 1.2 Reconocer el acceso y el contrato HTTP durante la espera

La Function URL utiliza `AuthType: NONE` y admite invocación pública. El bucket mantiene bloqueo de acceso público. Lambda escribe las imágenes mediante su execution role.

El template incluye los permisos `lambda:InvokeFunctionUrl` y `lambda:InvokeFunction`. El segundo se limita a invocaciones mediante Function URL.

El cliente Python envía los bytes JPEG o PNG con su `Content-Type`. La Function URL los entrega a Lambda como base64 en `event.body`, con `isBase64Encoded: true`. El código proporcionado recupera los bytes antes de almacenarlos.

El máximo de 4 MiB permite incluir la codificación base64 y el resto del evento dentro del límite sincrónico de Lambda de 6 MiB. La aplicación comprueba tamaño, tipo y firma del archivo; los proveedores validan el contenido de la imagen.

#### 1.3 Obtener las salidas y cargar el ZIP

1. Abra el stack `tel351-mpr` y seleccione **Outputs**
2. Identifique los valores siguientes:

   | Key | Uso |
   | --- | --- |
   | `FunctionUrl` | Dirección pública que se configurará en el cliente Python |
   | `FunctionName` | Nombre de la función que se editará |
   | `DataBucketName` | Bucket donde se comprobarán las imágenes |
   | `LogGroupName` | Grupo de logs para diagnosticar solicitudes |

3. Abra **Lambda** y seleccione la función identificada por `FunctionName`
4. En **Code → Code source**, seleccione **Upload from → .zip file**
5. Seleccione **Upload**, elija el archivo preparado `lambda.zip` y guarde con **Save**
6. Espere a que termine la actualización y compruebe que el editor muestre `index.py`, `lambda_function.py`, `stages.py` y `normalization.py`
7. Abra **Configuration → Environment variables** y compruebe `LAB_STAGE` igual a `upload` y `DATA_BUCKET` igual al bucket del stack

La plantilla utiliza Python 3.14; conserve ese runtime y el handler configurado. La carga de ZIP desde la consola instala los módulos preparados; no es necesario comprimir archivos durante la actividad. Después de la carga, abra `FunctionUrl` seguida de `status` y compruebe HTTP `200` con `stage: "upload"`. Si persiste HTTP `503`, revise que se haya elegido el ZIP preparado y que la actualización haya terminado. Cargue ese ZIP una sola vez y complete después los ejercicios en el editor. Volver a cargar el ZIP inicial reemplazaría las modificaciones realizadas en Lambda.

#### 1.4 Configurar el cliente Python y enviar una imagen

1. Abra `client.py` en un editor de texto
2. Asigne a `LAMBDA_URL` el valor de `FunctionUrl` obtenido en el stack y guarde el archivo:

   ```python
   LAMBDA_URL = "https://<identificador>.lambda-url.us-east-1.on.aws/"
   ```

3. Abra una terminal en la carpeta donde guardó `client.py` y ejecute:

   ```bash
   python3 client.py "ruta/a/foto.jpg"
   ```

El único argumento es la ruta de la imagen, que puede ser absoluta o relativa a la carpeta desde la que ejecuta el comando. Si su instalación utiliza el comando `python`, úselo en lugar de `python3`.

El programa agrega `/analyze` a la URL, identifica el `Content-Type` de la imagen y envía sus bytes mediante `POST`. Espere la respuesta: el cliente imprime el JSON formateado y el estado HTTP. Si Lambda devuelve un error en JSON, también lo imprime para facilitar el diagnóstico. En las etapas siguientes, vuelva a ejecutar el mismo comando para enviar la fotografía.

#### 1.5 Comprobar la carga

1. Confirme HTTP `201` y una respuesta con un único campo, `imageKey`
2. Identifique en ese campo la key del objeto almacenado
3. Abra **S3 → Buckets** y seleccione el bucket indicado por `DataBucketName`
4. Abra `uploads/` y localice la key indicada por la respuesta
5. Compruebe que el objeto corresponda a la fotografía enviada

La respuesta tiene esta forma:

```json
{"imageKey": "uploads/<uuid>.jpg"}
```

Lambda genera un UUID v4 aleatorio representado por 32 caracteres hexadecimales, sin guiones. La extensión será `.jpg` o `.png`, según la imagen. Cada envío genera otro UUID y otro objeto, aunque se utilice la misma fotografía.

### 2. Integrar Cloud Vision

#### 2.1 Preparar Google Cloud y la API key

1. Abra Google Cloud Console y seleccione el proyecto que se utilizará
2. Compruebe en **Billing** que el proyecto tenga facturación habilitada
3. Abra **APIs & Services → Library**, busque **Cloud Vision API** y habilítela
4. Abra **APIs & Services → Credentials → Create credentials → API key** y cree una clave estándar del proyecto
5. Abra esa clave y, en **API restrictions**, seleccione **Restrict key** y autorice solamente **Cloud Vision API**
6. Conserve **Application restrictions: None**, porque la solicitud se realizará desde Lambda y no desde un navegador con HTTP referrer. Guarde los cambios

La API key identifica el proyecto consumidor del servicio. Lambda la utilizará para llamar a Vision; no se incorpora a la solicitud del cliente Python.

#### 2.2 Implementar la llamada HTTP a Vision

En Lambda, abra **Code → stages.py**. Complete `analyze_vision(image_bytes, api_key, max_labels=10)` reemplazando `raise NotImplementedError(...)`.

A partir de la documentación de Cloud Vision, determine:

1. El endpoint y el método HTTP para solicitar la detección de etiquetas de una imagen
2. La codificación de la imagen y la estructura del cuerpo de la solicitud
3. Cómo incorporar la API key a la solicitud
4. Cómo limitar la cantidad de etiquetas mediante `max_labels`

Implemente la construcción y el envío de la solicitud a partir de los argumentos recibidos. Lea la respuesta HTTP, decodifique su JSON y devuelva el diccionario original completo. Puede utilizar `base64`, `urllib.request` y `json`, incluidos en la biblioteca estándar. La función debe utilizar la imagen y la clave recibidas, sin valores fijos en el código.

El runtime proporciona la recepción de la imagen, el almacenamiento en S3 y el diagnóstico común de errores. La llamada HTTP a Vision y la lectura de su respuesta corresponden a esta función. `image_bytes` contiene los bytes originales de la fotografía, `api_key` contiene la clave y `max_labels` indica la cantidad máxima de etiquetas solicitada. Agregue los imports necesarios en `stages.py`.

Antes de probar, compruebe que la solicitud utiliza esos argumentos y que la función devuelve un diccionario, en lugar del objeto de respuesta HTTP o de una cadena JSON. Explique cómo se representa la imagen en la solicitud y dónde se incorpora la autenticación.

Guarde el archivo y seleccione **Deploy**. Espere la confirmación antes de probar.

#### 2.3 Configurar la clave y activar Vision

1. Abra **Configuration → Environment variables → Edit**
2. Agregue una variable mediante **Add environment variable**, si aún no existe:

   | Key | Value |
   | --- | --- |
   | `GOOGLE_API_KEY` | La API key preparada en el proyecto Google Cloud |

3. Ingrese personalmente la clave como valor de texto, sin comillas ni JSON
4. Cambie `LAB_STAGE` de `upload` a `vision`
5. Conserve `DATA_BUCKET` y las demás variables existentes
6. Seleccione **Save** y espere la actualización

El runtime lee `GOOGLE_API_KEY` mediante `os.environ` y entrega su valor a `analyze_vision`. Su implementación debe utilizar ese argumento para autenticar la solicitud. La clave no se escribe como un valor fijo en `stages.py`, en el template ni en `client.py`.

Compruebe `GET /status`: debe indicar `stage: "vision"`. En las etapas siguientes se modificará solamente `LAB_STAGE`, conservando la clave y el bucket.

#### 2.4 Verificar la comunicación AWS–Google Cloud

Vuelva a ejecutar `client.py` con la misma fotografía. Compruebe:

1. HTTP `200` y los campos `imageKey` y `vision`
2. La nueva imagen almacenada bajo la key indicada por `imageKey`
3. La respuesta original de Google directamente dentro de `vision`
4. La colección de etiquetas dentro de la respuesta de Vision; identifique el campo del nombre y el del puntaje de una etiqueta real
5. La llegada del resultado en esa misma llamada HTTP

En el mismo bucket S3, compruebe `uploads/<uuid>.vision.json`, utilizando el UUID de `imageKey`. Ese archivo contiene el mismo JSON que el campo `vision` de la respuesta y se guarda con `Content-Type: application/json`. La imagen original conserva su propia extensión.

Las etiquetas se devuelven en inglés. Una lista vacía puede ser válida; no equivale a un error de autenticación. Vision también puede devolver `responses[0].error` dentro de HTTP `200`; el código auxiliar reconoce esa condición como error del proveedor.

Conserve la respuesta y registre las decisiones de su implementación: endpoint, método, autenticación y representación de la imagen. Distinga la llamada del cliente a Lambda de la llamada que Lambda realiza a Vision. Continúe con Rekognition y la comparación para completar el laboratorio.

### 3. Amazon Rekognition

La integración con Vision se implementó y comprobó en la etapa anterior. En esta etapa se agrega únicamente la llamada a Rekognition, utilizando la misma Lambda y la misma imagen.

#### 3.1 Implementar la llamada a Rekognition

En **Code → stages.py**, complete `detect_rekognition(client, image_bytes, max_labels=10)` reemplazando `raise NotImplementedError(...)`.

El argumento `client` es un cliente Boto3 de Rekognition. Identifique la operación de detección de etiquetas y sus parámetros. Envíe los bytes originales de `image_bytes`, solicite hasta `max_labels` etiquetas y utilice el menor umbral de confianza permitido por la operación. Devuelva la respuesta original completa del SDK.

Determine qué transformación realiza Boto3 sobre la imagen antes de enviarla y evite aplicar esa transformación dos veces. La llamada utiliza las credenciales temporales del execution role; la API key de Google corresponde a la integración anterior.

Compare esta implementación con la llamada HTTP a Vision. Identifique qué tareas realiza el SDK y cuáles tuvo que implementar directamente en la integración anterior. Conserve la respuesta completa, incluida la información que no utilizará en la comparación.

Guarde el archivo, seleccione **Deploy** y espere la confirmación.

#### 3.2 Activar Rekognition e identificar el permiso pendiente

1. Abra **Configuration → Environment variables → Edit**
2. Cambie solamente `LAB_STAGE` a `rekognition`, conservando `DATA_BUCKET` y `GOOGLE_API_KEY`
3. Seleccione **Save** y espere la actualización
4. Compruebe `GET /status`
5. Vuelva a ejecutar `client.py` con la misma imagen

La plantilla no concede todavía `rekognition:DetectLabels`. Si el ejercicio está completo y Vision funciona, esta primera llamada devuelve HTTP `207`: conserva `imageKey` y `vision`, y presenta `errors.rekognition.code` igual a `AccessDeniedException`.

Compruebe que el análisis de Vision terminó y que se guardaron la imagen y su archivo `.vision.json`. Identifique el rechazo de permisos de Rekognition. La integración con Vision ya está implementada; conserve ese código y no interprete el rechazo como una lista vacía de etiquetas.

#### 3.3 Agregar el permiso y comprobar el análisis

1. En Lambda, abra **Configuration → Permissions**
2. Siga el enlace del **Execution role** para abrir el rol en IAM
3. En **Permissions**, seleccione **Add permissions → Create inline policy**
4. Seleccione el editor **JSON** e incorpore la policy siguiente:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": "rekognition:DetectLabels",
         "Resource": "*"
       }
     ]
   }
   ```

5. Avance, asigne el nombre `tel351-mpr-detect-labels` y cree la policy
6. Vuelva a ejecutar `client.py` con la misma fotografía

`DetectLabels` no admite restringirse al ARN de una imagen; por eso utiliza `Resource: "*"`. La policy autoriza esa operación, no la administración del servicio. No es necesario modificar el código para agregar el permiso.

Confirme ahora HTTP `200` y los campos `imageKey`, `vision` y `rekognition`. Lambda espera primero la respuesta de Vision y después la de Rekognition; el cliente recibe ambas respuestas originales al finalizar la secuencia. Las dos llamadas utilizan los mismos bytes de la imagen recibida.

En S3, localice los tres objetos del envío utilizando el mismo UUID:

- `uploads/<uuid>.jpg` o `.png`: imagen original
- `uploads/<uuid>.vision.json`: contenido del campo `vision`
- `uploads/<uuid>.rekognition.json`: contenido del campo `rekognition`

Los dos archivos JSON tienen `Content-Type: application/json`. Descargue o abra los resultados para comprobar que corresponden a los originales impresos por el cliente.

#### 3.4 Identificar los contratos de respuesta

Examine las respuestas reales de ambos proveedores. Para cada una, identifique:

- La colección que contiene las etiquetas detectadas
- Los campos que representan el nombre y el puntaje de cada etiqueta
- La escala del puntaje y su significado según el proveedor
- La información adicional que acompaña a las etiquetas

Construya una tabla con esos datos y un ejemplo de etiqueta obtenido de la fotografía enviada. Registre también cómo cada solicitud representa la imagen, limita la cantidad de etiquetas y se autentica. Utilice los contratos identificados para implementar los adaptadores de la etapa siguiente. Distinga las etiquetas detectadas directamente de otra información, como categorías o relaciones entre etiquetas.

Se solicitan hasta diez etiquetas por proveedor; esa cantidad máxima no implica que sus modelos o vocabularios sean equivalentes.

### 4. Adaptar y comparar los resultados

#### 4.1 Completar los dos adaptadores

En **Code → stages.py**, complete `normalize_vision(raw)` y `normalize_rekognition(raw)` reemplazando `raise NotImplementedError(...)` en ambas funciones.

Utilice los contratos que identificó para seleccionar la colección de etiquetas, los campos del nombre y del puntaje, y la escala de cada proveedor. Llame a `normalize_labels(items, provider, label_field, confidence_field, scale)` con esos datos y devuelva su resultado. Identifique al proveedor mediante `vision` o `rekognition`.

La normalización textual, la validación y la eliminación de duplicados ya están implementadas en `normalization.py`. Los adaptadores deben interpretar cada contrato sin modificar la respuesta original `raw` ni reescribir el normalizador.

El siguiente ejemplo sintético muestra la estructura de los objetos que entrega la función auxiliar:

```json
{
  "provider": "vision",
  "label": "Traffic light",
  "key": "traffic light",
  "confidence": 0.91,
  "originalConfidence": 0.91,
  "originalScale": "0-1"
}
```

`label` y `originalConfidence` conservan sus valores originales. `key` aplica Unicode NFKC, comparación sin distinción de mayúsculas y reducción de espacios. La función auxiliar conserva la primera etiqueta de cada key y omite entradas sin nombres o puntajes válidos.

El normalizador utiliza la escala que recibe para representar el puntaje entre 0 y 1 y conserva su valor original. **Compartir la escala 0–1 no demuestra equivalencia estadística entre los puntajes.** No promedie los puntajes de ambos proveedores ni los utilice para determinar cuál entrega el mejor resultado.

#### 4.2 Completar el comparador

Abra `compare_labels(vision_labels, rekognition_labels)`. El código inicial ya crea los índices y los conjuntos `vision_keys` y `rekognition_keys`. Reemplace los tres valores `None` por las operaciones correspondientes:

- `common_keys`: intersección de ambos conjuntos
- `only_vision_keys`: keys de Vision que no aparecen en Rekognition
- `only_rekognition_keys`: keys de Rekognition que no aparecen en Vision

Determine las operaciones entre conjuntos que corresponden a esos tres resultados. Conserve la comprobación `if any(...)` y la llamada final a `build_comparison`; la función auxiliar construye y ordena estos grupos:

| Campo | Contenido |
| --- | --- |
| `common` | Objetos con la key y los registros completos de ambos proveedores |
| `onlyVision` | Etiquetas presentes solamente en Vision |
| `onlyRekognition` | Etiquetas presentes solamente en Rekognition |

La coincidencia depende de la key textual normalizada. `Traffic Light` y ` traffic  light ` coinciden; `Car` y `Vehicle` quedan separados. Una etiqueta exclusiva significa que esa key no apareció en el resultado del otro proveedor, no que su modelo sea incapaz de reconocer el objeto.

Guarde los cambios de los adaptadores y comparador, seleccione **Deploy** y espere la confirmación.

#### 4.3 Comparar los resultados para la misma fotografía

1. En **Configuration → Environment variables → Edit**, cambie solamente `LAB_STAGE` a `compare`
2. Conserve `DATA_BUCKET` y `GOOGLE_API_KEY`, seleccione **Save** y espere
3. Compruebe `GET /status`
4. Vuelva a ejecutar `client.py` con la misma fotografía utilizada en las etapas anteriores
5. Revise los resultados siguientes:

   | Campo | Comprobación |
   | --- | --- |
   | `imageKey` | Identifica la imagen de este envío |
   | `vision` | Conserva el contrato original de Google |
   | `rekognition` | Conserva el contrato original de AWS |
   | `comparison` | Contiene `common`, `onlyVision` y `onlyRekognition`, con los registros normalizados |

6. Compruebe en S3 la imagen y los dos JSON originales asociados al UUID de `imageKey`
7. Identifique etiquetas comunes y exclusivas de esa misma fotografía; algún grupo puede quedar vacío
8. Explique una diferencia considerando nombres, nivel de detalle o selección de etiquetas. Indique también por qué los puntajes no son estadísticamente equivalentes

Conserve una respuesta real con ambos resultados originales, sus registros normalizados y la comparación como evidencia final. La respuesta de Vision permite comprobar la integración inicial. La comprobación final requiere también la respuesta de Rekognition, los resultados normalizados y la comparación.

## Limpieza posterior

Realice la limpieza **después de terminar el laboratorio**:

1. Conserve las respuestas e imágenes propias necesarias como evidencia
2. Abra **CloudFormation → Stacks → tel351-mpr → Outputs** e identifique nuevamente `DataBucketName`; anote también `LogGroupName` antes de eliminar el stack
3. Abra **S3 → Buckets**, seleccione ese bucket y revise sus objetos
4. Seleccione **Empty**, confirme el nombre o texto solicitado por la consola y espere que termine el vaciado. Esta operación elimina las imágenes y resultados JSON de ese bucket; compruebe que corresponda al laboratorio
5. Regrese al stack `tel351-mpr`, seleccione **Delete** y confirme
6. Espere la eliminación y compruebe que desaparecieron Function URL, Lambda, bucket y execution role
7. Si aparece `DELETE_FAILED`, revise **Events**, resuelva la causa informada y repita la eliminación
8. Abra **CloudWatch → Logs → Log groups**, seleccione exclusivamente el grupo anotado en `LogGroupName` y elimínelo. Lambda lo crea automáticamente; no forma parte de los recursos administrados por este stack
9. En **Google Cloud Console → APIs & Services → Credentials**, elimine la API key creada para el laboratorio

Eliminar Lambda retira su copia de la variable de entorno, pero no revoca la API key en Google. Conserve el proyecto Google Cloud, billing, credenciales preexistentes, identidad administrativa AWS y recursos de otros laboratorios.
