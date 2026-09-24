# QR DEKAL

## Lancement local

Backend:
```bash
cd backend
pip install -r requirements.txt
python app.py
```

User:
```bash
cd frontend-user
python -m http.server 8000
```

Admin:
```bash
cd frontend-admin
python -m http.server 8001
```

URLs:
- User: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8001/login.html
- Création du premier admin: http://127.0.0.1:8001/setup.html
- Accès direct au dashboard: http://127.0.0.1:8001/direct.html
- API: http://127.0.0.1:5000/api/health

## Publicités

Dans Admin → Publicités, importer une image ou une vidéo. Les vidéos sont configurées en autoplay, inline et loop. Les navigateurs mobiles peuvent bloquer l'autoplay avec son : la vidéo démarre donc automatiquement en muet, puis le bouton « Activer le son » permet d'activer l'audio après interaction de l'utilisateur.
