import os
import re
import webbrowser
import sublime
import sublime_plugin
import subprocess

HOSTINGS = {
    'github': {
        'url': 'https://github.com/{user}/{repo}/blob/{revision}/{remote_path}{filename}',
        'blame_url': 'https://github.com/{user}/{repo}/blame/{revision}/{remote_path}{filename}',
        'line_param': '#L',
        'line_param_sep': '-L'
    },
    'bitbucket': {
        'url': 'https://bitbucket.org/{user}/{repo}/src/{revision}/{remote_path}{filename}',
        'blame_url': 'https://bitbucket.org/{user}/{repo}/annotate/{revision}/{remote_path}{filename}',
        'line_param': '#cl-',
        'line_param_sep': ':'
    },
    'gitlab': {
        'url': 'https://{domain}/{user}/{repo}/-/blob/{revision}/{remote_path}{filename}',
        'blame_url': 'https://{domain}/{user}/{repo}/-/blame/{revision}/{remote_path}{filename}',
        'line_param': '#L',
        'line_param_sep': '-'
    }
}


class GitlinkCommand(sublime_plugin.TextCommand):

    def getoutput(self, command):
        out, err = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True).communicate()
        return out.decode().strip()

    def run(self, edit, **args):
        # Current file path & filename

        # only works on current open file
        path, filename = os.path.split(self.view.file_name())

        # Switch to cwd of file
        os.chdir(path + "/")

        # Find the remote of the current branch
        branch_name = self.getoutput("git branch --show-current")
        remote_name = self.getoutput(
            "git config --get branch.{}.remote".format(branch_name)
        )
        remote = self.getoutput("git remote get-url {}".format(remote_name))
        remote = re.sub('.git$', '', remote)

        # Use ssh, except when the remote url starts with http:// or https://
        use_ssh = re.match(r'^https?://', remote) is None
        if use_ssh:
            # Below index lookups always succeed, nu matter whether the split
            # character exists
            domain = remote.split(':', 1)[0].split('@', 1)[-1]
            # `domain` may be an alias configured in ssh
            try:
                ssh_output = self.getoutput("ssh -G " + domain)
            except:  # noqa intended unconditional except
                # This is just an attempt at being smart. Let's not crash if
                # it didn't work
                pass
            if ssh_output:
                match = re.search(r'hostname (.*)', ssh_output, re.MULTILINE)
                if match:
                    domain = match.group(1)
            _ignored, user, repo = remote.replace(":", "/").split("/")
            del _ignored
        else:
            # HTTP repository
            # format is {domain}/{user}/{repo}.git
            domain, user, repo = remote.split("/")

        # Select the right hosting configuration
        for hosting_name, hosting in HOSTINGS.items():
            if hosting_name in remote:
                # We found a match, so keep these variable assignments
                break

        # Find top level repo in current dir structure
        remote_path = self.getoutput("git rev-parse --show-prefix")

        # Find the current revision
        revision = self.getoutput("git rev-parse HEAD")

        # Choose the view type we'll use
        if 'blame' in args and args['blame']:
            view_type = 'blame_url'
        else:
            view_type = 'url'

        # Build the URL
        url = hosting[view_type].format(domain=domain, user=user, repo=repo, revision=revision, remote_path=remote_path, filename=filename)

        if args['line']:
            region = self.view.sel()[0]
            first_line = self.view.rowcol(region.begin())[0] + 1
            last_line = self.view.rowcol(region.end())[0] + 1
            if first_line == last_line:
                url += "{0}{1}".format(hosting['line_param'], first_line)
            else:
                url += "{0}{1}{2}{3}".format(hosting['line_param'], first_line, hosting['line_param_sep'], last_line)

        if args['web']:
            webbrowser.open_new_tab(url)
        else:
            sublime.set_clipboard(url)
            sublime.status_message('Git URL has been copied to clipboard')
