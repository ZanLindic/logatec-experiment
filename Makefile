#
#   Main Makefile
#

DEPLOY_LOCATION=deployment/ansible

ci:
	#$(DEPLOY_LOCATION)/deploy_targets
	#$(DEPLOY_LOCATION)/deploy_controller
	#TODO

cd: 
	$(DEPLOY_LOCATION)/compile_apk
	$(DEPLOY_LOCATION)/release_targets
	$(DEPLOY_LOCATION)/release_controller
	$(DEPLOY_LOCATION)/collect_results

.PHONY: cd 
