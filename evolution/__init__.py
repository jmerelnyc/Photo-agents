"""Self-evolution / reflection scripts for the Photo Agents runtime.

The ``runtime --reflect <script>`` mode loads a Python module from this
package (or any path) and polls its ``check()`` function on a fixed
``INTERVAL``. When ``check()`` returns a non-empty string, that string is
fed to the agent as a new task.
"""
