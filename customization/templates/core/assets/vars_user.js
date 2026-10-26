{% if request.args.get('portal') == '1' %}
{{ {'user': {'id': user_vars.id, 'name': user_vars.fullName or user_vars.identifier} if user_vars else none, 'csrf_token': session.csrf_token, 'language': session.lang or 'zh_Hans_CN'} | tojson }}
{% else %}
Indico.User = {{ user_vars | tojson }};
{% endif %}
