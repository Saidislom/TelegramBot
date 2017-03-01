import yaml


def load_config(config_path):
    """
    parser yml file to dict
    :param config_path: the _config.yml file path
    :return: dict of yml parser
    """
    if isinstance(config_path, str):
        return yaml.load(open(config_path, mode='r'))
    else:
        return


def use_yml_config(yml_dict):
    """
    judge whether use yml config
    :param yml_dict:
    :return:  True if use yml config,False use shell
    """
    if isinstance(yml_dict, dict) and 'use_yml' in yml_dict:
        result_use = yml_dict['use_yml']
        if isinstance(result_use, bool):
            return result_use
        else:
            return False


def check_config(yml_dict):
    """
    check yml params
    :param yml_dict:
    :return: True if yml config correct otherwise False
    """
    for index in yml_dict:
        node_result = yml_dict[index]
        if isinstance(node_result, dict):
            check_config(node_result)
        elif node_result is not None:
            continue
        else:
            return False
    return True


if __name__ == '__main__':
    dict_result = load_config('./_config.yml')
    print(dict_result)
    print(use_yml_config(dict_result))
