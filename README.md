# ProductionCloud_LocalFilesClient
LocalFilesClient syncs products and folders from the ProductionCloud into the PC for local editing.

### Beta
This is a recent project and its not a vital part of the server hence it has not been fully develop nor tested. We don't recommend its use for important files or projects neither its use in a production line. For that we recommend our interactive web form. With this said we have found this tools very useful for locally editing drawing CAD files since most of them rely on Windows CAD software.

### Install
**Windows**  
 1. [Download Windows 64 executable file from GitHub.](https://github.com/dfmdmx/ProductionCloud_LocalFilesClient/blob/master/dist/LocalFilesClient.exe)
 2. Double click to run.

**Linux and Windows with Python source**  
 1. [Download source ZIP project from GitHub.](https://github.com/dfmdmx/ProductionCloud_LocalFilesClient/archive/master.zip)
 2. Unzip the file and cd into the recently extracted folder named `ProductionCloud_LocalFilesClient-master`.
 3. Type `python3 LocalFilesClient.py` in order to run the script.

The client will then ask for a login and a directory to place the files. Go to My-Cloud in the Production Server and refresh the webpage. A new dropdown named `Local Files` should now appear under My-Cloud header menu. The connections takes a pair of minutes.

Right click any Cloud product and select 'send to local folder' in order to sync it locally with the client.

**Note:** Google users will need to create a server password. To create one, instead of login in using the Google button type your email in the site login form and click on forgot password. A mail will be send to you asking for a new password.
