# Procfile — Comando de startup para OpenShift (Source-to-Image / S2I)
#
# O OpenShift usa este arquivo para determinar como iniciar a aplicação.
# O comando abaixo inicia o Gunicorn com toda a configuração de gunicorn.conf.py.
#
# Documentação: https://docs.openshift.com/container-platform/latest/openshift_images/s2i_images/python.html

web: gunicorn -c gunicorn.conf.py app:app
