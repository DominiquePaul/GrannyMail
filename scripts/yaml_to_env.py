import yaml


def yaml_to_env(yaml_file, env_file):
    with open(yaml_file, "r") as f:
        data = yaml.safe_load(f)

    with open(env_file, "w") as f:
        for key, value in data.items():
            line = f"{key.upper()}={value}\n"
            f.write(line)


# Replace 'input.yaml' with the path to your YAML file
yaml_to_env("dev.yaml", "dev.env")
yaml_to_env("stage.yaml", "stage.env")
yaml_to_env("prod.yaml", "prod.env")
