import pathlib
from invoke import task
import subprocess
import yaml
import os
import json


def get_env_var(env_var):
    """
    Get environment variable from .env file
    :param env_var:
    :return:
    """
    var = os.environ.get(env_var)
    if not var:
        var = input(f"Environment variable {env_var} not found. Please provide a value: ")
        os.environ[env_var] = var
        update_env_yaml(env_var, var)
        update_env_descriptions(env_var)
    return var


def update_env_yaml(env_var, value):
    """
    Update environment.yaml file with the new environment variable
    :param env_var:
    :param value:
    :return:
    """
    yaml_file = './environment.yaml'
    if os.path.exists(yaml_file):
        with open(yaml_file, 'r') as file:
            env_dict = yaml.safe_load(file) or {}
    else:
        env_dict = {}

    env_dict[env_var] = value

    with open(yaml_file, 'w') as file:
        yaml.dump(env_dict, file)


def update_env_descriptions(env_var):
    """
    Update the descriptions of environment variables in a JSON file
    :param env_var:
    :return:
    """
    descriptions_file = './env_descriptions.json'
    if os.path.exists(descriptions_file):
        with open(descriptions_file, 'r') as file:
            descriptions = json.load(file)
    else:
        descriptions = {}

    if env_var not in descriptions:
        description = input(f"Please provide a description for the environment variable {env_var}: ")
        descriptions[env_var] = description

        with open(descriptions_file, 'w') as file:
            json.dump(descriptions, file, indent=4)


@task
def install(c):
    """
    install requirements.txt
    :param c:
    :return:
    """
    print("Installing requirements.txt...")
    subprocess.run(["pip", "install", "-r", "requirements.txt"])


@task
def installdev(c):
    """
    install requirements-dev.txt and requirements.txt
    :param c:
    :return:
    """
    print("Installing requirements-dev.txt...")
    subprocess.run(["pip", "install", "-r", "requirements-dev.txt"])
    install(c)


@task
def dockerbuild(c):
    """
    run docker daemon if not already running and build the docker image
    :return:
    """
    print("Building docker image...")
    # print current working directory
    subprocess.run(["docker", "build", "-t", get_env_var('IMAGE_NAME'), "-f", "docker/Dockerfile", "."])


@task
def dockertag(c):
    """
    tag the docker image
    :return:
    """
    docker_tag = f"{get_env_var('DOCKER_USERNAME')}/{get_env_var('IMAGE_NAME')}:latest"
    print("Tagging docker image...")
    subprocess.run(["docker", "tag", get_env_var('IMAGE_NAME'), docker_tag])
    print(f"Tagged docker image: {docker_tag}")


@task
def dockerpush(c):
    """
    push the docker image to dockerhub
    :return:
    """
    dockerlogin(c)
    docker_tag = f"{get_env_var('DOCKER_USERNAME')}/{get_env_var('IMAGE_NAME')}:latest"
    print("Pushing docker image to DockerHub...")
    subprocess.run(["docker", "push", docker_tag])


@task
def dockerlogin(c):
    """
    login to dockerhub
    :return:
    """
    print("Logging into DockerHub...")
    subprocess.run(["docker", "login", "-u", get_env_var('DOCKER_USERNAME'), "-p", get_env_var('DOCKER_TOKEN')])


@task
def docker(ctx, b=False, t=False, p=False):
    """
    build, tag, and push the docker image to dockerhub
    usage: inv docker -b -t -p
    :return:
    """
    if b:
        dockerbuild(ctx)
    if t:
        dockertag(ctx)
    if p:
        dockerpush(ctx)


@task
def dockerpull(c):
    """
    pull the docker image from dockerhub
    :return:
    """
    print("Pulling docker image from DockerHub...")
    full_tag = f"{get_env_var('DOCKER_USERNAME')}/{get_env_var('IMAGE_NAME')}:latest"
    subprocess.run(["docker", "pull", full_tag])
    print(f"Pulled docker image: {full_tag}")


@task
def gcrdeploy(c):
    """
    Deploy the docker image to Google Cloud Run.
    :return:
    """
    print("Deploying docker image to Google Cloud Run...")
    tag = 'latest'
    docker_username = get_env_var('DOCKER_USERNAME')
    image_name = get_env_var('IMAGE_NAME')
    docker_tag = f'docker.io/{docker_username}/{image_name}:{tag}'
    envtoyaml(c)
    command = [
        'gcloud',
        'run',
        'deploy',
        get_env_var('IMAGE_NAME'),
        '--image',
        docker_tag,
        '--region',
        'us-east1',
        '--no-allow-unauthenticated',
        '--project',
        get_env_var('GCR_PROJECT_ID'),
        '--env-vars-file',
        './env.yaml'
    ]
    subprocess.run(command, check=True, shell=True)


@task
def envtoyaml(c):
    """
    Convert .env file to YAML file
    :param c:
    :return:
    """
    env_dict = {}
    # Usage example
    env_file = './.env'
    yaml_file = './env.yaml'

    # Read the .env file and populate the dictionary
    with open(env_file, 'r') as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                env_dict[key] = value

    # Write the dictionary to a YAML file
    with open(yaml_file, 'w') as file:
        yaml.dump(env_dict, file)

    print(f"YAML file '{yaml_file}' created successfully.")


@task
def buildenvpy(c):
    """
    Requires: .env in the root directory
    Build the env_auto.py file from the variables in .env using this pattern:
    import os and dotenv at the top of the file
    include new line, then:
    for each line in .env, if the line is not empty and does not start with '#', then
    split the line on '=' and use the variable to write a line in env_auto.py:
    <variable> = os.environ.get('<variable>')
    :param c:
    :return:
    """
    with open('.env', 'r') as f:
        lines = f.readlines()
    pathlib.Path('env').mkdir(parents=True, exist_ok=True)
    with open('env/env_auto.py', 'w') as f:
        f.write(
            '"""\n'
            'Desc:\n'
            'env_auto.py is generated from .env by the `invoke buildenvpy` task.\n'
            'it\'s purpose is to provide IDE support for environment variables.\n'
            '"""\n'
            '\n'
            'import os\n'
            'from dotenv import load_dotenv\n'
            'load_dotenv()\n\n'
            '\n'
        )
        for line in lines:
            if line != '\n' and not line.startswith('#'):
                variable = line.split('=')[0]
                f.write(f'{variable} = os.environ.get(\'{variable}\')\n')
    print('env/env_auto.py built from .env')


@task
def dockerrun(c):
    """
    run the docker image with IMAGE_NAME and .env variables
    :param c:
    :return:
    """
    print("Running docker image...")
    subprocess.run(["docker", "run", "--env-file", ".env", get_env_var('IMAGE_NAME')])


@task
def cookiecutter(c):
    """
    run cookiecutter to create a new project
    :param c:
    :return:
    """
    print("Running cookiecutter...")
    project_name = get_env_var('PROJECT_NAME')
    package_name = get_env_var('PACKAGE_NAME')
    subprocess.run([
        "cookiecutter",
        "https://github.com/bjahnke/cookiecutter-python.git",
        "--no-input"
        f"project_name={project_name}",
        f"package_name={package_name}"
    ])
