from fabric.api import env, task, run, local, sudo, cd, prefix, prompt, get
from string import Template
import os
import sys

curr_dir = os.path.abspath(os.path.dirname(__file__))

APTGET_PACKAGES = [ "pkg-config",
        "postgresql", "libpq-dev", "vim", "libreadline6",
        "libreadline6-dev", "python-dev", "python-setuptools",
        "git",
        "python-pip", "python-virtualenv"
]

venv = lambda : "source {}".format(os.path.join(env.venv_path, "bin/activate"))
djapp = lambda : env.code_root

def setup_env():
    """
    decorator to set env variables based on the host
    """
    if env.venv_root:
        env.venv_path = os.path.join(env.venv_root, env.venv_name)
    else:
        env.venv_path = os.path.join(env.project_root, env.venv_name)
    
    env.code_root = os.path.join(env.project_root, env.project_name)

    path = os.path.abspath(os.path.join(os.path.dirname(__file__), env.project_name))
    sys.path.insert(0, path)


def _validate_user_input(value):
        if value not in ["Y", "y", "N", "n"]:
            raise Exception("Not a valid input. Available option: Y/N")
        else:
            value = value.upper() 
        return True if value=="Y" else False

@task
def print_fab_config():
    """
    prints sample fab config file
    """
    template_path = os.path.join(curr_dir, "templates", "fabconfig.conf")
    with open(template_path, "r") as template_file:
        print template_file.read()
    
    
@task
def rebuild(branch="master"):
    """
    uploads a new build for django project
    """
    setup_env()
#     install_sys_packages()
    with cd(djapp()):
        run("git checkout {} && git pull origin {}".format(branch, branch))
        update_requirements()
        sync_app()
        touch()

    
@task
def bootstrap():
    setup_env()
    proceed = prompt("Installing Sys Packages, You can skip this, by pressing n/N:",
                      default="Y", validate=_validate_user_input)
    if proceed: install_sys_packages()
    
    proceed = prompt("Setting up VirtualEnv, You can skip this, by pressing n/N:",
                      default="Y", validate=_validate_user_input)
    if proceed: 
        mkvenv()
        update_requirements()

    proceed = prompt("Generating Setting and Config files, You can skip this, by pressing n/N:",
                      default="Y", validate=_validate_user_input)
    if proceed:
        generate_local_settings()
        generate_apache_vh()
        generate_wsgi_script()
        generate_celery_conf()

    proceed = prompt("Setting up database, You can skip this, by pressing n/N:",
                      default="Y", validate=_validate_user_input)
    if proceed: setup_database()
    
    init_directories()
    sync_app()
    
    proceed = prompt("Loading Initial data, You can skip this, by pressing n/N:",
                      default="Y", validate=_validate_user_input)
    if proceed: load_initialdata()
    
    proceed = prompt("Initiaizing supervisor, You can skip this, by pressing n/N:",
                      default="Y", validate=_validate_user_input)
    if proceed: init_supervisor()
    
    proceed = prompt("Creating Apache symbolic link, You can skip this, by pressing n/N:",
                      default="Y", validate=_validate_user_input)
    if proceed: symbolik_link_apache()
    
    proceed = prompt("Creating Dajngo Super User, You can skip this, by pressing n/N:",
                      default="Y", validate=_validate_user_input)
    if proceed: createsuperuser()
    
    
@task
def createsuperuser():
    setup_env()
    with cd(djapp()):
        with prefix(venv()):
            run("python manage.py createsuperuser")

    
def generate_local_settings():
    print "Generating local settings file."
    template_path = os.path.join(env.project_root, "templates", "local_settings")
    context = {
        "project_name": env.project_name,
        "db_name": env.db_name,
        "db_user": env.db_user,
        "db_passwd": env.db_passwd,
        "admins": env.admins,
        "managers": env.managers,
        "allowed_hosts": env.allowed_hosts,
        "email_host": env.email_host,
        "email_port": env.email_port,
        "email_host_user": env.email_host_user,
        "email_host_passwd": env.email_host_passwd,
        "email_default_from_email": env.email_default_from_email,
        "static_root": env.static_root,
        "static_url": env.static_url,
        "media_root": env.media_root,
        "media_url": env.media_url
        
    }
    with open(template_path, "r") as template_file:
        template = Template(template_file.read())
        file_data = template.safe_substitute(context)
    settings_path = os.path.join(djapp(), env.project_name, "settings", "local_settings.py")
    with open(settings_path, "w+") as settings_file:
        settings_file.write(file_data)

    
def generate_apache_vh():
    print "Generating apache virtualhost config."
    template_path = os.path.join(env.project_root, "templates", "apache_vh.conf")
    context = {
        "project_root": env.project_root,
        "apache_server_name": env.apache_server_name,
        "apache_server_alias": env.apache_server_alias,
        "apache_server_admin_email": env.apache_server_admin_email
    }
    with open(template_path, "r") as template_file:
        template = Template(template_file.read())
        file_data = template.safe_substitute(context)
    file_path = os.path.join(djapp(), "apache", env.project_name+ ".conf")
    with open(file_path, "w+") as new_file:
        new_file.write(file_data)


def generate_wsgi_script():
    print "Generating wsgi script"
    template_path = os.path.join(env.project_root, "templates", "wsgi")
    context = {
        "venv_path": env.venv_path,
        "project_name": env.project_name
    }
    with open(template_path, "r") as template_file:
        template = Template(template_file.read())
        file_data = template.safe_substitute(context)
    file_path = os.path.join(djapp(), env.project_name, "wsgi.py")
    with open(file_path, "w+") as new_file:
        new_file.write(file_data)


def generate_celery_conf():
    print "Generating celery config"
    template_path = os.path.join(env.project_root, "templates", "celeryd.conf")
    context = {
        "code_dir": env.code_root,
        "log_dir":env.log_dir,
        "user":env.user,
        "venv_path": env.venv_path,
        "project_name": env.project_name,
        "celery_log_dir": env.celery_log_dir
    }
    with open(template_path, "r") as template_file:
        template = Template(template_file.read())
        file_data = template.safe_substitute(context)
    file_path = os.path.join(env.project_root, "celeryd.conf")
    with open(file_path, "w+") as new_file:
        new_file.write(file_data)


def setup_database():
    """
    Create Database and database user, using django settings
    """
    from fabutil import select_db_type
    from fabutil.utils import add_user

    def _validate_user_input(value):
        if value not in ["Y", "y", "N", "n"]:
            raise Exception("Not a valid input. Available option: Y/N")
        else:
            return value.upper()

    db_type_class = select_db_type()
    if db_type_class:
        db = db_type_class()
        db_password = db.install()
#         from django.conf import settings
#         dbname = settings.DATABASES['default']["NAME"]
        dbname = env.db_name
        password = env.db_passwd
        user = env.db_user
        feedback = prompt("Do you want to create a Database user: {} with password: {}. [Y/N]".format(user, password),
                          default="N", validate=_validate_user_input)
        if feedback == "Y":
            db.create_db_and_user(dbname, user, password)
        else:
            db.create_db(dbname)
        db.grant_privileges(dbname, user)


def symbolik_link_apache():
    """
    """
    apache_site_dir = "/etc/apache2/sites-available"
    virtualhostfilename = "{}.conf".format(env.project_name)
    virtualhost_file_in_app = os.path.join(djapp(), "apache", virtualhostfilename)
    apachevhostfilepath = os.path.join(apache_site_dir, virtualhostfilename)
    with cd(apache_site_dir):
        sudo("ln -s {} {}".format(virtualhost_file_in_app, apachevhostfilepath))
        sudo("a2ensite {}".format(virtualhostfilename))
    apache_reload()
    

def install_sys_packages():
    sudo("apt-get update")
    sudo("apt-get install %s" % " ".join(APTGET_PACKAGES))


def mkvenv():
    print "making virtualenv"
    args = '--distribute'
    run('virtualenv %s %s' % (args, env.venv_path))
 
    
def update_requirements():
    """ update external dependencies on remote host """
    print "installing python packages"
    with cd(env.project_root):
        with prefix(venv()):
            run("pip install -r requirements.txt")
    

def sync_app():
    """
    """
    print "sync application"
    with cd(djapp()):
        with prefix(venv()):
            run("python manage.py syncdb")
            run("python manage.py migrate --all")
            run("python manage.py syncdb --all")# this helps  create permissions meta
            run("python manage.py collectstatic  --noinput")
            run("python manage.py compress --force")


def touch():
    """ touch wsgi file to trigger reload """
    wsgi_path = os.path.join(djapp(), env.project_name, 'wsgi.py')
    run('touch {}'.format(wsgi_path))


def init_supervisor():
    """
    """
    supervisor_conf_file = os.path.join(env.project_root, "supervisord.conf")
    with prefix(venv()):
        run("supervisord -c {}".format(supervisor_conf_file))
    
    
def load_initialdata():
    data_files = [
                  "fixtures/initial/dbmail.xml",
                  "fixtures/initial/config.xml",
                  "fixtures/initial/configsettings.xml"]
    # "fixtures/initial/main.xml"
    with cd(djapp()):
        with prefix(venv()):
            run("python manage.py init_project")
            for i in data_files:
                run("python manage.py loaddata {}".format(i))
                

def init_directories():
    """
    Create app dirs and set correct permissions
    """
    run("mkdir -p {}".format(env.log_dir))
    run("mkdir -p {}".format(env.celery_log_dir))
    run("mkdir -p {}".format(env.media_root))
    run("chmod -R 777 {}".format(env.media_root))
    
    
@task
def apache_reload():
    """ reload Apache on remote host """
 #   sudo('/etc/init.d/apache2 reload')


def setup_code():
    """
    download code from git repo and unpack in project root
    """
    print "Setting project path and downloading code"
    run("mkdir -p {}".format(env.project_root))
    with cd(env.project_root):
        run("git clone {} {}".format(env.git_repo, '.') )
    

@task
def django_manage(cmd):
    setup_env()
    with cd(djapp()):
        with prefix(venv()):
            run("python manage.py {}".format(cmd))    