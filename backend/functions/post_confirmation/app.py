import boto3

cognito = boto3.client("cognito-idp")


def lambda_handler(event, context):
    if event.get("triggerSource") == "PostConfirmation_ConfirmSignUp":
        cognito.admin_add_user_to_group(
            UserPoolId=event["userPoolId"],
            Username=event["userName"],
            GroupName="Farmers",
        )
    return event
