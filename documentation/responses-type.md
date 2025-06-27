# Endpoint 1: POST /token

## Request Body

```json
{
  "grant_type": "secret",
  "client_id": "OOONA_CLIENT_ID",
  "client_secret": "OOONA_CLIENT_SECRET",
  "secret": "OOONA_API_KEY",
  "name": "OOONA_API_NAME"
}
```

## Responses Type

### 200

```json
{
  "access_token": "string",
  "token_type": "string",
  "expires_in": "integer",
  "refresh_token": "string",
  "id": "string",
  "userName": "string",
  "email": "string",
  "phone": "string",
  "trial": "boolean",
  "twoFactorEnabled": "boolean",
  "googleAuthenticatorEnabled": "boolean",
  "country": "string",
  "clientId": "string",
  "ip": "string",
  "dateCreated": "integer",
  "nearestExpiration": "integer",
  "identificationToken": "string",
  "isPersistent": "boolean",
  "showcase": "boolean",
  "roles": ["string"],
  ".refresh": "boolean",
  ".issued": "string",
  ".expires": "string"
}
```

# Endpoint 2: POST /external/convert/[importId]/[exportId]

## Request Headers

- `Authorization`: string (value = "Bearer [access_token]")

### Path Parameters

- `importId`: string (value = "srt")
- `exportId`: string (value = "ooona")

### Request Body

- File

## Responses Type

### 200

- OOONA JSON
