# engineering-thesis

Deployment tips for Printer Fleet Manager App:

1. Clone the repository from Github using `git clone https://github.com/Jacek-Kapral/engineering-thesis.git`
2. Edit .env.example file and fill in the required data as per comments.
3. Save .env.example in the root folder of the app as .env
4. Choose which mail parser script You prefer to use (pop3 or imap) from folder /mailparser_example_scripts/ and copy it over mailparser.py in root folder of the app.
5. Run the app using docker compose up --build.
6. Open TCP:5000 port on firewall if needed.
7. If You prefer different port, change it in Dockerfile and docker-compose.yml
8. Enjoy using the app!


Comment:
If You've forgotten the admin password, deploy the app again,
or use /reset_password if You've put down Your real e-mail address.
